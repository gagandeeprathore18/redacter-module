import fitz # PyMuPDF
import re
import json
from redact_engine import (
    redact_text, is_logo_match, 
    STUDENT_ID_PATTERN, EMAIL_PATTERN, PHONE_PATTERN, POSTAL_CODE_PATTERN,
    DOMAIN_PATTERNS, SUBMISSION_FEEDBACK_DATE_PATTERN,
    DATE_TIME_ONLY_PATTERN, TABLE_ROW_KEYWORD_PATTERN,
    NAME_PROXIMITY_PATTERN, NAME_PATTERN, TABLE_ROW_NAME_KEYWORD_PATTERN,
    is_likely_human_name, URL_OR_DOMAIN_PATTERN, EDUCATIONAL_KEYWORDS,
    TABLE_ROW_LOCATION_KEYWORD_PATTERN, SUBMISSION_LOCATION_PATTERN
)
from redaction.stop_patterns import should_stop_block
from redaction.protected_zone_detector import reset_protected_zone, set_protected_zone

def should_stop_location_block(line: str) -> bool:
    """Delegates to the shared stop-block checker."""
    return should_stop_block(line)

def get_text_match_rects(page, target_text: str):
    """
    Finds contiguous sequences of words on the page whose concatenated clean alphanumeric
    text matches target_text. Merges overlapping same-line rects and expands them slightly
    to prevent leaving traces of leading/trailing commas/punctuation.
    """
    target_clean = re.sub(r'[^\w]', '', target_text.lower())
    if not target_clean:
        return []
        
    page_words = page.get_text("words")
    rects = []
    
    n_words = len(page_words)
    for i in range(n_words):
        current_str = ""
        span_rects = []
        for j in range(i, min(i + 15, n_words)):
            w = page_words[j]
            word_clean = re.sub(r'[^\w]', '', w[4].lower())
            if not word_clean:
                continue
            current_str += word_clean
            span_rects.append(fitz.Rect(w[0], w[1], w[2], w[3]))
            
            if current_str == target_clean:
                if span_rects:
                    merged_rect = span_rects[0]
                    for r in span_rects[1:]:
                        if abs(r.y0 - merged_rect.y0) < 5:
                            merged_rect = merged_rect | r
                        else:
                            merged_rect.x0 = max(0, merged_rect.x0 - 8)
                            merged_rect.x1 = merged_rect.x1 + 8
                            rects.append(merged_rect)
                            merged_rect = r
                    merged_rect.x0 = max(0, merged_rect.x0 - 8)
                    merged_rect.x1 = merged_rect.x1 + 8
                    rects.append(merged_rect)
                break
            elif len(current_str) > len(target_clean):
                break
    return rects

def redact_pdf_table_rows(page):
    """
    Finds labels matching TABLE_ROW_KEYWORD_PATTERN or TABLE_ROW_LOCATION_KEYWORD_PATTERN
    on the page, and redacts the entire value cell area to their right, leaving no traces.
    """
    page_words = page.get_text("words")
    if not page_words:
        return
        
    # Group words by line (approximate y-coordinate alignment within 5 points)
    page_words.sort(key=lambda w: (w[1], w[0]))
    
    lines = []
    current_line = []
    current_y0 = -1
    
    for w in page_words:
        y0 = w[1]
        if current_y0 == -1:
            current_y0 = y0
            current_line.append(w)
        elif abs(y0 - current_y0) < 5:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
            current_y0 = y0
    if current_line:
        lines.append(current_line)
        
    for line in lines:
        line.sort(key=lambda w: w[0])
        n_words = len(line)
        i = 0
        while i < n_words:
            matched_len = 0
            matched_type = None
            
            # Match contiguous phrases of length 1 to 8 words
            for l in range(min(8, n_words - i), 0, -1):
                phrase = " ".join(line[i+k][4] for k in range(l))
                phrase_clean = phrase.strip()
                if TABLE_ROW_KEYWORD_PATTERN.search(phrase_clean):
                    matched_len = l
                    matched_type = "date"
                    break
                elif TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(phrase_clean):
                    matched_len = l
                    matched_type = "location"
                    break
                    
            if matched_len > 0:
                label_words = line[i:i+matched_len]
                label_rect = fitz.Rect(
                    label_words[0][0],
                    min(w[1] for w in label_words),
                    label_words[-1][2],
                    max(w[3] for w in label_words)
                )
                
                # Find the next label on the same line to the right
                next_label_x0 = page.rect.x1 - 30  # Default to right margin
                for j in range(i + matched_len, n_words):
                    is_next_label = False
                    for l_next in range(1, min(5, n_words - j + 1)):
                        next_phrase = " ".join(line[j+k][4] for k in range(l_next))
                        if (TABLE_ROW_KEYWORD_PATTERN.search(next_phrase) or 
                            TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(next_phrase) or
                            TABLE_ROW_NAME_KEYWORD_PATTERN.search(next_phrase)):
                            is_next_label = True
                            break
                    if is_next_label:
                        next_label_x0 = line[j][0]
                        break
                        
                if next_label_x0 > label_rect.x1 + 10:
                    # Draw a solid white box over the entire value cell region
                    value_rect = fitz.Rect(
                        label_rect.x1 + 2,
                        label_rect.y0 - 2,
                        next_label_x0 - 2,
                        label_rect.y1 + 2
                    )
                    page.add_redact_annot(value_rect, fill=(1, 1, 1))
                    
                i += matched_len
            else:
                i += 1

def process_pdf(input_path: str, output_path: str):
    from redaction.ownership_manager import clear_issuing_university, determine_issuing_university, get_active_patterns
    clear_issuing_university()
    
    doc = fitz.open(input_path)
    
    # 1. Preliminary scan to count image occurrences and build metadata
    image_metadata_map = {} # hash -> list of dicts (page_num, rect, width, height, xref)
    image_counts = {}       # hash -> repeat_count
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img_hash = hash(image_bytes)
                
                rects = page.get_image_rects(xref)
                for rect in rects:
                    width = rect.x1 - rect.x0
                    height = rect.y1 - rect.y0
                    
                    # Estimate location: header if in top 15%, footer if in bottom 15%
                    page_height = page.rect.y1 - page.rect.y0
                    location = "body"
                    if rect.y1 < page_height * 0.15:
                        location = "header"
                    elif rect.y0 > page_height * 0.85:
                        location = "footer"
                        
                    meta = {
                        "page": page_num + 1,
                        "location": location,
                        "width": width,
                        "height": height,
                        "rect": rect,
                        "xref": xref,
                        "bytes": image_bytes
                    }
                    if img_hash not in image_metadata_map:
                        image_metadata_map[img_hash] = []
                    image_metadata_map[img_hash].append(meta)
                    image_counts[img_hash] = image_counts.get(img_hash, 0) + 1
            except Exception:
                pass

    # 2. Run branding evaluation on unique images
    images_to_redact = set()
    try:
        # Import branding modules (ensure sys.path includes drafter-module root if needed)
        import sys
        import os
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        from branding.image_preprocessor import preprocess_image
        from branding.ocr_detector import OCRDetector
        from branding.branding_decision import BrandingDecisionEngine
        
        ocr = OCRDetector()
        decision_engine = BrandingDecisionEngine()
        
        for img_hash, occurrences in image_metadata_map.items():
            first_occ = occurrences[0]
            img_meta = {
                "location": first_occ["location"],
                "page": first_occ["page"],
                "width": first_occ["width"],
                "height": first_occ["height"],
                "repeat_count": image_counts[img_hash]
            }
            
            # Preprocess image and run OCR
            preprocessed_bytes = preprocess_image(first_occ["bytes"])
            ocr_text = ocr.extract_text(preprocessed_bytes)
            
            should_remove, score, breakdown = decision_engine.evaluate_image(img_meta, ocr_text)
            print(f"PDF Evaluated image {first_occ['xref']}: score={score}, ocr='{ocr_text}', decision={'REMOVE' if should_remove else 'KEEP'}, breakdown={breakdown}")
            
            # Determine issuing university from logo OCR text
            determine_issuing_university(ocr_text)
            
            if should_remove or is_logo_match(first_occ["bytes"]):
                images_to_redact.add(img_hash)
    except Exception as e:
        print(f"Error during PDF branding detection: {e}")
        # Fallback to simple is_logo_match
        for img_hash, occurrences in image_metadata_map.items():
            if is_logo_match(occurrences[0]["bytes"]):
                images_to_redact.add(img_hash)

    # 2.5. Scan pass for LLM Escalations
    from redaction.escalation_manager import clear_cache, register_candidate_scan, run_gpt_review, get_document_metrics
    from redaction.entity_classifier import classify_entity
    from redaction.ownership_manager import get_issuing_university
    
    clear_cache()
    reset_protected_zone()
    
    # We scan all page texts for potential human name candidates or other entities
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        set_protected_zone(page_text)
        normalized_text = re.sub(r'[ \t\r\f\v]+', ' ', page_text)
        normalized_text = re.sub(r'\n+', '\n', normalized_text)
        
        # Scan for Proximity Names
        for match in NAME_PROXIMITY_PATTERN.finditer(normalized_text):
            name_str = match.group(1).strip()
            if name_str and len(name_str) > 2:
                classification, action, reasons, score = classify_entity(name_str, context=match.group(0))
                register_candidate_scan(name_str, match.group(0), classification, action, score, reasons)
                
        # Scan for general Names if name keyword exists
        if TABLE_ROW_NAME_KEYWORD_PATTERN.search(normalized_text):
            for match in NAME_PATTERN.finditer(normalized_text):
                name_str = match.group(0).strip()
                if name_str and len(name_str) > 2:
                    start_idx = max(0, match.start() - 120)
                    end_idx = min(len(normalized_text), match.end() + 120)
                    context = normalized_text[start_idx:end_idx]
                    classification, action, reasons, score = classify_entity(name_str, context=context)
                    register_candidate_scan(name_str, context, classification, action, score, reasons)

    # Run the GPT batch review if there are escalated candidates
    issuing_univ = get_issuing_university()
    doc_id = os.path.basename(input_path)
    run_gpt_review(issuing_university=issuing_univ, doc_id=doc_id)
    
    # Log passive telemetry metrics
    metrics = get_document_metrics(doc_id)
    print(f"Hybrid classification metrics: {json.dumps(metrics)}")

    # Define a helper list of patterns to match text and their replacements
    patterns = [
        (STUDENT_ID_PATTERN, " "),
        (EMAIL_PATTERN, " "),
        (PHONE_PATTERN, " "),
        (POSTAL_CODE_PATTERN, " "),
        (SUBMISSION_FEEDBACK_DATE_PATTERN, " ")
    ]
    # Add active patterns of the ISSUING_UNIVERSITY only
    for p in get_active_patterns():
        patterns.append((p, " "))
        
    reset_protected_zone()
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 1. Redact Text
        page_text = page.get_text("text")
        set_protected_zone(page_text)
        # Reconstruct space-normalized text for page, collapsing horizontal spaces but preserving newlines
        normalized_text = re.sub(r'[ \t\r\f\v]+', ' ', page_text)
        normalized_text = re.sub(r'\n+', '\n', normalized_text)

        # Find unique matches in the normalized page text to redact
        matches_to_redact = []
        for pattern, replacement in patterns:
            for match in pattern.finditer(normalized_text):
                matched_str = match.group(0).strip()
                if matched_str and len(matched_str) > 2:
                    matches_to_redact.append((matched_str, replacement))
                    
        # Find educational URLs to redact in normalized text ONLY if they match ISSUING_UNIVERSITY
        for match in URL_OR_DOMAIN_PATTERN.finditer(normalized_text):
            matched_str = match.group(0).strip()
            belongs_to_issuing = False
            for pattern in get_active_patterns():
                if pattern.search(matched_str):
                    belongs_to_issuing = True
                    break
            if belongs_to_issuing:
                matches_to_redact.append((matched_str, " "))
                
        # Apply proximity-based date/time search in normalized text
        # Use ±300 char window (up from 120) so dates at paragraph ends are caught
        for match in DATE_TIME_ONLY_PATTERN.finditer(normalized_text):
            matched_str = match.group(0).strip()
            if matched_str and len(matched_str) > 2:
                start_idx = max(0, match.start() - 300)
                end_idx = min(len(normalized_text), match.end() + 300)
                context = normalized_text[start_idx:end_idx]
                if TABLE_ROW_KEYWORD_PATTERN.search(context):
                    matches_to_redact.append((matched_str, " "))
                    
        # Apply proximity-based name search in normalized text
        has_proximity_match = False
        for match in NAME_PROXIMITY_PATTERN.finditer(normalized_text):
            name_str = match.group(1).strip()
            if name_str and len(name_str) > 2 and is_likely_human_name(name_str, context=match.group(0)):
                matches_to_redact.append((name_str, " "))
                has_proximity_match = True
                
        # If the page text contains a name keyword, check context in normalized text
        if TABLE_ROW_NAME_KEYWORD_PATTERN.search(normalized_text) and not has_proximity_match:
            for match in NAME_PATTERN.finditer(normalized_text):
                name_str = match.group(0).strip()
                if name_str and len(name_str) > 2:
                    start_idx = max(0, match.start() - 120)
                    end_idx = min(len(normalized_text), match.end() + 120)
                    context = normalized_text[start_idx:end_idx]
                    if is_likely_human_name(name_str, context=context):
                        if TABLE_ROW_NAME_KEYWORD_PATTERN.search(context):
                            matches_to_redact.append((name_str, " "))

        # Split lines for line-by-line submission location continuation scanning
        lines = page_text.split('\n')
        lines = [line.strip() for line in lines]

        # Apply line-by-line submission location detection — blank the label and ALL
        # continuation lines (Option A, Option B, etc.) that follow until the next
        # non-empty label line (a line with a colon that looks like a new field).
        # Use TABLE_ROW_LOCATION_KEYWORD_PATTERN (label-only, no trailing .*).
        in_location_block = False
        for i, line in enumerate(lines):
            if line and TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(line):
                matches_to_redact.append((line, " "))
                in_location_block = True
            elif in_location_block:
                if not line:
                    continue
                if should_stop_location_block(line):
                    in_location_block = False
                else:
                    matches_to_redact.append((line, " "))

        # Apply search and redaction annotations for matched strings
        for matched_str, replacement in set(matches_to_redact):
            rects = get_text_match_rects(page, matched_str)
            if not rects:
                rects = page.search_for(matched_str)
            for rect in rects:
                # Add redaction annotation
                page.add_redact_annot(rect, text=replacement, fill=(1, 1, 1))

        # Blank out date/location table value cells geometrically
        redact_pdf_table_rows(page)

        # 2. Redact Hyperlinks
        links = page.get_links()
        for link in links:
            uri = link.get("uri", "")
            if uri:
                # Check if URI matches any patterns
                should_redact_link = False
                for pattern, _ in patterns:
                    if pattern.search(uri):
                        should_redact_link = True
                        break
                # Also check educational URL pattern ONLY if it matches ISSUING_UNIVERSITY
                if not should_redact_link:
                    if URL_OR_DOMAIN_PATTERN.search(uri):
                        for pattern in get_active_patterns():
                            if pattern.search(uri):
                                should_redact_link = True
                                break
                if should_redact_link:
                    # Delete the hyperlink
                    page.delete_link(link)

        # 3. Redact Logos/Images
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img_hash = hash(image_bytes)
                if img_hash in images_to_redact:
                    # Get all rects where this image is placed on the page
                    rects = page.get_image_rects(xref)
                    for rect in rects:
                        # Redact the image location by overlaying a white box
                        page.add_redact_annot(rect, fill=(1, 1, 1))
            except Exception:
                pass
                
        # Apply all redactions on this page
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
        
    doc.save(output_path, garbage=3, deflate=True)
    doc.close()
