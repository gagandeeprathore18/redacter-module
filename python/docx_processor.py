import docx
import re
from PIL import Image
import io
import os
import json
from redact_engine import (
    redact_text, is_logo_match, redact_paragraph_runs,
    DATE_TIME_ONLY_PATTERN, redact_paragraph_runs_with_pattern,
    TABLE_ROW_KEYWORD_PATTERN, TABLE_ROW_NAME_KEYWORD_PATTERN,
    SAFE_COLUMN_HEADER_PATTERN,
    TABLE_ROW_LOCATION_KEYWORD_PATTERN, SUBMISSION_LOCATION_PATTERN
)
from redaction.stop_patterns import should_stop_block

from redaction.table_parser import normalize_table
from redaction.target_detector import detect_targets
from redaction.relationship_detector import get_block_coordinates
from redaction.block_extractor import extract_block_cells
from redaction.block_redactor import redact_cell
from redaction.validator import validate_table_redaction
from redaction.docx_structure_analyzer import analyze_and_redact_runs
from redaction.header_footer_processor import process_docx_headers_footers
from redaction.protected_zone_detector import reset_protected_zone, set_protected_zone

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
}

def get_all_paragraph_runs(p):
    runs = []
    # Find all w:r elements recursively to capture runs nested in hyperlinks
    for r_el in p._element.findall('.//w:r', NAMESPACES):
        runs.append(docx.text.run.Run(r_el, p))
    return runs

def get_blank_image_bytes() -> bytes:
    img = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def process_paragraph(p, redact_all_dates=False, redact_all_names=False, blank_entire=False, context=""):
    """Process a paragraph's runs. If blank_entire is True, wipe all run text."""
    runs = get_all_paragraph_runs(p)
    if not runs:
        return
    if blank_entire:
        for run in runs:
            run.text = " "
        return
    # Run structural run-combining analysis and redaction
    redact_paragraph_runs(runs, redact_all_dates=redact_all_dates, redact_all_names=redact_all_names, context=context)

def process_table(table):
    # 1. Run Relationship-based Submission Location Redaction Engine
    grid = normalize_table(table)
    target_coords = detect_targets(grid)
    all_block_coords = set()
    for coord in target_coords:
        block = get_block_coordinates(grid, coord)
        all_block_coords.update(block)
        
    if all_block_coords:
        cells_to_redact = extract_block_cells(grid, all_block_coords)
        for cell in cells_to_redact:
            redact_cell(cell, is_docx=True)
        final_grid = normalize_table(table)
        validate_table_redaction(grid, final_grid, all_block_coords)

    # Get column headers if available
    headers = []
    if len(table.rows) > 0:
        for cell in table.rows[0].cells:
            headers.append("".join(p.text for p in cell.paragraphs).strip())

    for row_idx, row in enumerate(table.rows):
        # Keyword scanning
        row_has_keyword = False
        row_has_name_keyword = False
        row_has_location_keyword = False
        label_cell_idx = -1
        date_label_cell_indices = set()

        # The "label" cell is always the first unique cell in column 0.
        label_cell_text = ""
        if row.cells:
            label_cell_text = "".join(p.text for p in row.cells[0].paragraphs).strip()

        for idx, cell in enumerate(row.cells):
            # If this cell is part of the relationship-redacted block, skip scanning it
            if (row_idx, idx) in all_block_coords:
                continue
            cell_text = "".join(p.text for p in cell.paragraphs).strip()
            if TABLE_ROW_KEYWORD_PATTERN.search(cell_text):
                row_has_keyword = True
                date_label_cell_indices.add(idx)
            if TABLE_ROW_NAME_KEYWORD_PATTERN.search(cell_text):
                row_has_name_keyword = True
                label_cell_idx = idx
            if TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(cell_text):
                row_has_location_keyword = True

        # Cell processing
        for idx, cell in enumerate(row.cells):
            # If cell was redacted by the relationship engine, skip it
            if (row_idx, idx) in all_block_coords:
                continue

            cell_text = "".join(p.text for p in cell.paragraphs).strip()
            set_protected_zone(cell_text)

            # Submission location rows: blank ALL cells entirely (label + value)
            if row_has_location_keyword:
                for p in cell.paragraphs:
                    set_protected_zone(p.text)
                    process_paragraph(p, blank_entire=True)
                for sub_table in cell.tables:
                    process_table(sub_table)
                continue

            is_safe_column = False
            if idx < len(headers):
                if SAFE_COLUMN_HEADER_PATTERN.search(headers[idx]):
                    is_safe_column = True

            # Only redact dates if this is NOT a safe column
            redact_dates_in_cell = row_has_keyword and not is_safe_column

            # Submission date/time value cells: blank entirely for symmetry
            if redact_dates_in_cell and idx not in date_label_cell_indices:
                for p in cell.paragraphs:
                    set_protected_zone(p.text)
                    process_paragraph(p, blank_entire=True)
                for sub_table in cell.tables:
                    process_table(sub_table)
                continue

            # Only run redact_all_names if this is NOT the label cell
            redact_names_in_cell = row_has_name_keyword and (idx != label_cell_idx)
            for p in cell.paragraphs:
                set_protected_zone(p.text)
                process_paragraph(p, redact_all_dates=redact_dates_in_cell, redact_all_names=redact_names_in_cell, context=label_cell_text if label_cell_text else "Name")

            # Recursively process sub-tables
            for sub_table in cell.tables:
                process_table(sub_table)

def should_stop_paragraph_block(text: str) -> bool:
    """Delegates to the shared stop-block checker."""
    return should_stop_block(text)

BLOCK_WIPE_LOCATION_PATTERN = re.compile(
    r'\b(?:'
    r'submission\s+(?:location|point|portal|platform|link|method|box|folder|area|mode|type|system|channel|url|address|site|page|form)'
    r'|submit(?:ted)?\s+(?:to|via|through|using|on|at|by|with)'
    r'|how\s+to\s+submit'
    r'|where\s+to\s+submit'
    r'|electronic(?:ally)?\s+submit(?:ted)?'
    r'|online\s+submission'
    r'|e-?submission'
    r'|upload\s+(?:location|link|portal|to)'
    r'|submission\s+details'
    r')\b',
    re.IGNORECASE
)

def is_paragraph_target(text: str) -> bool:
    if not text:
        return False
    if BLOCK_WIPE_LOCATION_PATTERN.search(text):
        return True
    from redaction.target_detector import BUSINESS_REMOVALS
    from redaction.normalizer import normalize_text
    from redaction.fuzzy_matcher import is_fuzzy_match
    norm_text = normalize_text(text)
    for clean_target in BUSINESS_REMOVALS:
        if is_fuzzy_match(norm_text, clean_target, threshold=85.0, partial=True):
            return True
    return False

def process_docx(input_path: str, output_path: str):
    doc = docx.Document(input_path)
    
    # Register document context for the redaction debug logger
    from redaction.redaction_debug_logger import set_document_context
    set_document_context(document=os.path.basename(input_path), source="docx")

    # 0. Clear and Determine Issuing University first from logos
    from redaction.ownership_manager import clear_issuing_university, determine_issuing_university
    clear_issuing_university()
    
    images_to_remove = []
    try:
        from branding.image_extractor import extract_images_from_docx
        from branding.image_preprocessor import preprocess_image
        from branding.ocr_detector import OCRDetector
        from branding.branding_decision import BrandingDecisionEngine
        
        extracted_images = extract_images_from_docx(doc)
        if extracted_images:
            ocr = OCRDetector()
            decision_engine = BrandingDecisionEngine()
            
            for img in extracted_images:
                preprocessed_bytes = preprocess_image(img["bytes"])
                ocr_text = ocr.extract_text(preprocessed_bytes)
                should_remove, score, breakdown = decision_engine.evaluate_image(img, ocr_text)
                
                print(f"Evaluated image {img['rId']}: score={score}, ocr='{ocr_text}', decision={'REMOVE' if should_remove else 'KEEP'}, breakdown={breakdown}")
                
                # Determine issuing university from logo OCR text
                determine_issuing_university(ocr_text)
                
                if should_remove:
                    images_to_remove.append(img)
    except Exception as ocr_err:
        print(f"Error during pre-scan: {ocr_err}")
    
    # 0.5. Scan pass for LLM Escalations
    from redaction.escalation_manager import clear_cache, register_candidate_scan, run_gpt_review, get_document_metrics
    from redaction.entity_classifier import classify_entity
    from redaction.ownership_manager import get_issuing_university
    
    clear_cache()
    reset_protected_zone()
    
    def scan_element_text(text, context=""):
        if not text or not text.strip():
            return
        set_protected_zone(text)
        classification, action, reasons, score = classify_entity(text, context=context)
        register_candidate_scan(text, context, classification, action, score, reasons)

    # Paragraphs scan
    for p in doc.paragraphs:
        set_protected_zone(p.text)
        scan_element_text(p.text)
        
    # Tables scan
    def scan_table(t):
        for row in t.rows:
            for cell in row.cells:
                cell_text = "".join(p.text for p in cell.paragraphs).strip()
                scan_element_text(cell_text)
                for p in cell.paragraphs:
                    scan_element_text(p.text)
                for sub_t in cell.tables:
                    scan_table(sub_t)
                    
    for table in doc.tables:
        scan_table(table)
        
    # Headers & Footers scan
    for section in doc.sections:
        if section.header:
            for p in section.header.paragraphs:
                scan_element_text(p.text)
            for table in section.header.tables:
                scan_table(table)
        if section.footer:
            for p in section.footer.paragraphs:
                scan_element_text(p.text)
            for table in section.footer.tables:
                scan_table(table)
                
    # Run the GPT batch review if there are escalated candidates
    issuing_univ = get_issuing_university()
    doc_id = os.path.basename(input_path)
    run_gpt_review(issuing_university=issuing_univ, doc_id=doc_id)
    
    # Log passive telemetry metrics
    metrics = get_document_metrics(doc_id)
    print(f"Hybrid classification metrics: {json.dumps(metrics)}")
    
    # 1. Redact Paragraphs
    reset_protected_zone()
    in_location_block = False
    for p in doc.paragraphs:
        set_protected_zone(p.text)
        para_text = p.text.strip()
        if not para_text:
            if in_location_block:
                process_paragraph(p, blank_entire=True)
            continue
            
        if is_paragraph_target(para_text):
            process_paragraph(p, blank_entire=True)
            in_location_block = True
        elif in_location_block:
            if should_stop_paragraph_block(para_text):
                in_location_block = False
                process_paragraph(p)
            else:
                process_paragraph(p, blank_entire=True)
        else:
            process_paragraph(p)
        
    # 2. Redact Tables
    for table in doc.tables:
        process_table(table)
        
    # 3. Redact Headers and Footers using specialized processor
    process_docx_headers_footers(doc, process_paragraph, process_table)

    # 4. Redact Hyperlink URLs
    for rel_id, rel in doc.part.rels.items():
        if "hyperlink" in rel.reltype:
            rel._target = redact_text(rel._target)

    # 5. Remove marked logo images
    from branding.logo_remover import remove_logo_inplace
    for img in images_to_remove:
        try:
            remove_logo_inplace(img)
        except Exception as e:
            print(f"Error removing logo image: {e}")

    doc.save(output_path)
