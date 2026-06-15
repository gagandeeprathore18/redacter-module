import fitz # PyMuPDF
import re
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

def should_stop_location_block(line: str) -> bool:
    """Delegates to the shared stop-block checker."""
    return should_stop_block(line)

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
        
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 1. Redact Text
        page_text = page.get_text("text")
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
            rects = page.search_for(matched_str)
            for rect in rects:
                # Add redaction annotation
                page.add_redact_annot(rect, text=replacement, fill=(1, 1, 1))

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
