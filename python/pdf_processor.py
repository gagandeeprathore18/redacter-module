import fitz # PyMuPDF
import re
import os
import json
from redact_engine import (
    redact_text, is_logo_match, 
    STUDENT_ID_PATTERN, EMAIL_PATTERN, PHONE_PATTERN, POSTAL_CODE_PATTERN,
    DOMAIN_PATTERNS,
    NAME_PROXIMITY_PATTERN, NAME_PATTERN, TABLE_ROW_NAME_KEYWORD_PATTERN,
    is_likely_human_name, URL_OR_DOMAIN_PATTERN, EDUCATIONAL_KEYWORDS,
    TABLE_ROW_LOCATION_KEYWORD_PATTERN, SUBMISSION_LOCATION_PATTERN,
    METADATA_FIELD_PATTERN
)
from redaction.stop_patterns import should_stop_block
from redaction.protected_zone_detector import reset_protected_zone, set_protected_zone

def padded_redaction_rect(page, rect, x_pad=0.8, y_pad=1.6):
    padded = fitz.Rect(rect.x0 - x_pad, rect.y0 - y_pad, rect.x1 + x_pad, rect.y1 + y_pad)
    return padded & page.rect

def _is_label_cell(text: str, max_words: int = 8) -> bool:
    """Helper to check if string looks like a short form label, not prose."""
    words = text.split()
    if len(words) > max_words:
        return False
    stripped = text.strip().rstrip('.')
    if re.search(r'\.\s+[A-Z]', stripped):
        return False
    return True

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
        prev_y0 = None
        for j in range(i, min(i + 15, n_words)):
            w = page_words[j]
            if prev_y0 is not None and abs(w[1] - prev_y0) > 8:
                break
            word_clean = re.sub(r'[^\w]', '', w[4].lower())
            if not word_clean:
                continue
            current_str += word_clean
            span_rects.append(fitz.Rect(w[0], w[1], w[2], w[3]))
            prev_y0 = w[1]
            
            if current_str == target_clean:
                print(f"DEBUG: matched target_clean={target_clean}, span_rects={span_rects}, w_list={[page_words[k] for k in range(i, j+1)]}")
                if span_rects:
                    merged_rect = span_rects[0]
                    for r in span_rects[1:]:
                        if abs(r.y0 - merged_rect.y0) < 5:
                            merged_rect = merged_rect | r
                        else:
                            rects.append(merged_rect)
                            merged_rect = r
                    rects.append(merged_rect)
                break
            elif len(current_str) > len(target_clean):
                break
    return rects

def detect_dominant_page_color(page) -> tuple[float, float, float]:
    """
    Renders the page to a pixmap, samples the four corner pixels, and calculates
    the dominant color. Returns RGB as float tuple in range [0.0, 1.0].
    """
    try:
        pix = page.get_pixmap()
        width = pix.width
        height = pix.height
        
        offset_x = min(10, max(1, width // 4))
        offset_y = min(10, max(1, height // 4))
        coords = [
            (offset_x, offset_y),
            (width - offset_x - 1, offset_y),
            (offset_x, height - offset_y - 1),
            (width - offset_x - 1, height - offset_y - 1)
        ]
        
        colors = []
        for x, y in coords:
            if 0 <= x < width and 0 <= y < height:
                p = pix.pixel(x, y)
                colors.append(p[:3])
                
        if not colors:
            return (1.0, 1.0, 1.0)
            
        from collections import Counter
        most_common_color, _ = Counter(colors).most_common(1)[0]
        return (most_common_color[0] / 255.0, most_common_color[1] / 255.0, most_common_color[2] / 255.0)
    except Exception as e:
        print(f"Error detecting page background color: {e}")
        return (1.0, 1.0, 1.0)

def detect_local_bg_color(page, rect, page_pix=None) -> tuple[float, float, float]:
    """
    Detects the background color around a specific rect on the page by sampling
    pixels from the page pixmap OUTSIDE the rect boundaries.
    This avoids sampling dark text glyph pixels that bias the result.
    """
    if page_pix is None:
        return (1.0, 1.0, 1.0)
    try:
        width = page_pix.width
        height = page_pix.height
        page_rect = page.rect

        # Map page coordinates to pixmap pixel coordinates
        rx0 = int((rect.x0 - page_rect.x0) * (width / page_rect.width))
        ry0 = int((rect.y0 - page_rect.y0) * (height / page_rect.height))
        rx1 = int((rect.x1 - page_rect.x0) * (width / page_rect.width))
        ry1 = int((rect.y1 - page_rect.y0) * (height / page_rect.height))

        # Clamp to pixmap boundaries
        rx0 = max(0, min(rx0, width - 1))
        ry0 = max(0, min(ry0, height - 1))
        rx1 = max(0, min(rx1, width - 1))
        ry1 = max(0, min(ry1, height - 1))

        colors = []
        # Margin in pixels to sample OUTSIDE the rect
        margin = 5

        # Sample pixels along a ring just OUTSIDE the rect boundaries
        # Top edge (above the rect)
        sample_y_top = max(0, ry0 - margin)
        for x in range(rx0, rx1 + 1, max(1, (rx1 - rx0) // 8)):
            x = min(x, width - 1)
            if 0 <= x < width and 0 <= sample_y_top < height:
                colors.append(page_pix.pixel(x, sample_y_top)[:3])

        # Bottom edge (below the rect)
        sample_y_bot = min(height - 1, ry1 + margin)
        for x in range(rx0, rx1 + 1, max(1, (rx1 - rx0) // 8)):
            x = min(x, width - 1)
            if 0 <= x < width and 0 <= sample_y_bot < height:
                colors.append(page_pix.pixel(x, sample_y_bot)[:3])

        # Left edge (left of the rect)
        sample_x_left = max(0, rx0 - margin)
        for y in range(ry0, ry1 + 1, max(1, (ry1 - ry0) // 4)):
            y = min(y, height - 1)
            if 0 <= sample_x_left < width and 0 <= y < height:
                colors.append(page_pix.pixel(sample_x_left, y)[:3])

        # Right edge (right of the rect)
        sample_x_right = min(width - 1, rx1 + margin)
        for y in range(ry0, ry1 + 1, max(1, (ry1 - ry0) // 4)):
            y = min(y, height - 1)
            if 0 <= sample_x_right < width and 0 <= y < height:
                colors.append(page_pix.pixel(sample_x_right, y)[:3])

        # Also sample the four corners just outside the rect
        corners = [
            (max(0, rx0 - margin), max(0, ry0 - margin)),
            (min(width - 1, rx1 + margin), max(0, ry0 - margin)),
            (max(0, rx0 - margin), min(height - 1, ry1 + margin)),
            (min(width - 1, rx1 + margin), min(height - 1, ry1 + margin)),
        ]
        for cx, cy in corners:
            if 0 <= cx < width and 0 <= cy < height:
                colors.append(page_pix.pixel(cx, cy)[:3])

        # Filter out dark pixels (likely text strokes or borders)
        bg_colors = [c for c in colors if sum(c) > 200]
        if not bg_colors:
            # Relax threshold if all samples are dark
            bg_colors = [c for c in colors if sum(c) > 100]
        if not bg_colors:
            bg_colors = colors

        if not bg_colors:
            return (1.0, 1.0, 1.0)

        from collections import Counter
        most_common, _ = Counter(bg_colors).most_common(1)[0]
        return (most_common[0] / 255.0, most_common[1] / 255.0, most_common[2] / 255.0)
    except Exception as e:
        print(f"Error detecting local bg color: {e}")
        return (1.0, 1.0, 1.0)

def get_text_style_for_rect(page, rect):
    # Default fallback style
    style = {
        "fontname": "helv",
        "fontsize": 11,
        "text_color": (0, 0, 0),
        "origin": (rect.x0, rect.y1 - 2)
    }
    try:
        text_page = page.get_text("dict")
        best_overlap = 0.0
        best_span = None
        
        for block in text_page.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_rect = fitz.Rect(span["bbox"])
                    overlap = (rect & span_rect).get_area()
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_span = span
                        
        if best_span:
            original_font = best_span.get("font", "").lower()
            is_bold = "bold" in original_font or "black" in original_font or "heavy" in original_font
            is_italic = "italic" in original_font or "oblique" in original_font
            
            if "times" in original_font:
                if is_bold and is_italic:
                    fontname = "timesbi"
                elif is_bold:
                    fontname = "timesb"
                elif is_italic:
                    fontname = "timesi"
                else:
                    fontname = "times"
            elif "cour" in original_font:
                if is_bold and is_italic:
                    fontname = "courbi"
                elif is_bold:
                    fontname = "courb"
                elif is_italic:
                    fontname = "couri"
                else:
                    fontname = "cour"
            else:
                if is_bold and is_italic:
                    fontname = "helvbo"
                elif is_bold:
                    fontname = "helvb"
                elif is_italic:
                    fontname = "helvo"
                else:
                    fontname = "helv"
                    
            style["fontname"] = fontname
            style["fontsize"] = best_span.get("size", 11)
            style["origin"] = best_span.get("origin", (rect.x0, rect.y1 - 2))
            
            color_int = best_span.get("color", 0)
            r = ((color_int >> 16) & 255) / 255.0
            g = ((color_int >> 8) & 255) / 255.0
            b = (color_int & 255) / 255.0
            style["text_color"] = (r, g, b)
    except Exception as e:
        print(f"Error extracting style for rect: {e}")
    return style

def redact_pdf_table_rows(page, fill_color=(1, 1, 1)):
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
                if TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(phrase_clean):
                    matched_len = l
                    matched_type = "location"
                    break
                    
            if matched_len > 0:
                phrase = " ".join(line[i+k][4] for k in range(matched_len))
                # Guard: only treat as a form label if it starts near the beginning of
                # the line (≤2 preceding words) AND is short enough to be a label.
                # This prevents firing on academic prose mid-sentence.
                if i > 2 or not _is_label_cell(phrase):
                    i += matched_len
                    continue
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
                        if (TABLE_ROW_LOCATION_KEYWORD_PATTERN.search(next_phrase) or
                            TABLE_ROW_NAME_KEYWORD_PATTERN.search(next_phrase)):
                            is_next_label = True
                            break
                    if is_next_label:
                        next_label_x0 = line[j][0]
                        break
                        
                if next_label_x0 > label_rect.x1 + 10:
                    # Geometrical cell-wide redaction disabled to ensure precise text-only redaction bounds.
                    pass
                    
                i += matched_len
            else:
                i += 1

def process_pdf(input_path: str, output_path: str):
    os.environ["CURRENT_DOCUMENT_ID"] = os.path.basename(input_path)
    from redaction.ownership_manager import clear_issuing_university, determine_issuing_university, get_active_patterns
    from redaction.redaction_debug_logger import set_document_context, log_redaction as _log_redaction
    clear_issuing_university()

    doc_name = os.path.basename(input_path)
    set_document_context(document=doc_name, source="pdf")

    def _log_pdf(candidate: str, classification: str, page_num: int, rect, block_text: str = ""):
        """Helper: convert fitz.Rect → bbox list and emit a debug log entry."""
        try:
            bbox = [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
        except Exception:
            bbox = None
        _log_redaction(
            candidate=candidate,
            classification=classification,
            page=page_num,
            bbox=bbox,
            ocr_block_text=block_text,
        )
    
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
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        from branding.image_preprocessor import preprocess_image
        from branding.branding_decision import BrandingDecisionEngine
        from image_processing.pipeline import process_raster_image
        from redaction.redaction_audit import RedactionAudit
        
        decision_engine = BrandingDecisionEngine()
        image_ocr_results = {}
        
        for img_hash, occurrences in image_metadata_map.items():
            first_occ = occurrences[0]
            img_meta = {
                "location": first_occ["location"],
                "page": first_occ["page"],
                "width": first_occ["width"],
                "height": first_occ["height"],
                "repeat_count": image_counts[img_hash]
            }
            
            # Advanced Image Processing Pipeline
            res = process_raster_image(first_occ["bytes"], first_occ["location"])
            image_ocr_results[img_hash] = res
            ocr_text = res["ocr_text"]
            
            # Log pre-processing metrics
            RedactionAudit.log({
                "candidate": f"[IMAGE xref={first_occ['xref']}]",
                "stage": "IMAGE_PRE_PROCESSING",
                "classification": "IMAGE",
                "decision": "KEEP",
                "ocr_words_detected": res["ocr_words_detected"],
                "char_map_entries": res["char_map_entries"],
                "screenshot_ui_detected": res["screenshot_ui_detected"],
                "screenshot_ui_cropped": 1 if res["screenshot_ui_detected"] else 0,
            })
            
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
        page_height = page.rect.y1 - page.rect.y0
        header_height = page_height * 0.20
        
        # Scan only header/footer regions (top 18% and bottom 18%) of page text to find issuing university
        header_footer_texts = []
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, block_text, block_no, block_type = block
            if y1 < page_height * 0.18 or y0 > page_height * 0.82:
                header_footer_texts.append(block_text)
        if header_footer_texts:
            combined_hf_text = "\n".join(header_footer_texts)
            norm_hf_text = re.sub(r'[ \t\r\f\v]+', ' ', combined_hf_text)
            norm_hf_text = re.sub(r'\n+', '\n', norm_hf_text)
            from redaction.ownership_manager import scan_text_for_universities
            scan_text_for_universities(norm_hf_text)

        # Step 4: Extract and filter out header contact/address blocks from scan text
        office_anchors = []
        postcode_anchors = []
        for block in page.get_text("blocks"):
            bx0, by0, bx1, by1, btext, bno, btype = block
            if btype == 0:
                text_lower = btext.lower()
                if any(k in text_lower for k in ["head office", "london office", "registered office", "office address"]):
                    office_anchors.append(fitz.Rect(bx0, by0, bx1, by1))
                if POSTAL_CODE_PATTERN.search(btext):
                    postcode_anchors.append(fitz.Rect(bx0, by0, bx1, by1))

        scan_block_texts = []
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, block_text, block_no, block_type = block
            if block_type == 0:  # text block
                y_center = (y0 + y1) / 2.0
                is_contact = any(k in block_text.lower() for k in ["www", "http", "email", "@", "telephone", "tel", "fax", "contact"])
                has_postcode = bool(POSTAL_CODE_PATTERN.search(block_text))
                has_keyword = any(k in block_text.lower() for k in ["street", "road", "avenue", "lane", "drive", "building", "house", "campus", "centre", "center", "park", "office", "gate"])
                is_multiline = "\n" in block_text.strip()
                
                is_address = has_postcode and (has_keyword or is_multiline)
                
                is_in_office_zone = False
                for anchor in office_anchors:
                    zone = fitz.Rect(anchor.x0 - 80, anchor.y1, anchor.x1 + 80, anchor.y1 + 140)
                    if zone.intersects(fitz.Rect(x0, y0, x1, y1)):
                        is_in_office_zone = True
                        break
                        
                is_in_postcode_zone = False
                for anchor in postcode_anchors:
                    zone = fitz.Rect(anchor.x0 - 80, anchor.y0 - 140, anchor.x1 + 80, anchor.y0)
                    if zone.intersects(fitz.Rect(x0, y0, x1, y1)):
                        is_in_postcode_zone = True
                        break
                
                has_explicit_office = any(k in block_text.lower() for k in ["head office", "london office", "registered office", "office address"])
                is_header_footer_contact = is_contact and (y_center < header_height or y_center > page_height * 0.80)
                
                is_keyword_match = any(k in block_text.lower() for k in ["street", "road", "avenue", "lane", "drive", "building", "house", "campus", "centre", "center", "park", "office", "gate", "london", "nottingham", "manchester", "oxford", "bucks", "leeds", "birmingham", "tel", "phone", "email", "@", "www", "http", "contact"]) or has_postcode
                
                is_valid_address = is_address or has_explicit_office or ((is_in_office_zone or is_in_postcode_zone) and is_keyword_match)
                
                if is_header_footer_contact or is_valid_address:
                    # Bypasses scan & GPT entirely
                    continue
            scan_block_texts.append(block_text)
            
        page_text_for_scan = "\n".join(scan_block_texts)
        set_protected_zone(page_text_for_scan)

        normalized_text = re.sub(r'[ \t\r\f\v]+', ' ', page_text_for_scan)
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

        # Scan for Date Candidates
        from redaction.date_time_detector import find_date_time_spans
        for start, end, matched_str, m_type in find_date_time_spans(normalized_text):
            if m_type == "DATE":
                matched_str = matched_str.strip()
                if matched_str and len(matched_str) > 2:
                    start_idx = max(0, start - 120)
                    end_idx = min(len(normalized_text), end + 120)
                    context = normalized_text[start_idx:end_idx]
                    classification, action, reasons, score = classify_entity(
                        matched_str, 
                        context=context, 
                        source_detector="DATE_CANDIDATE_PATTERN"
                    )
                    register_candidate_scan(matched_str, context, classification, action, score, reasons)

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
        (METADATA_FIELD_PATTERN, " ")
    ]
    # Add active patterns of the ISSUING_UNIVERSITY only
    for p in get_active_patterns():
        patterns.append((p, " "))
        
    # Always include Qualifi/Qualify patterns explicitly
    from redaction.ownership_manager import compile_flexible_pattern
    patterns.append((compile_flexible_pattern("Qualifi"), " "))
    patterns.append((compile_flexible_pattern("Qualify"), " "))
    patterns.append((re.compile(r'qualifi\.net', re.IGNORECASE), " "))
        
    reset_protected_zone()
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Get page pixmap once for dominant and local color detection
        try:
            page_pix = page.get_pixmap()
        except Exception:
            page_pix = None
            
        page_bg_color = detect_dominant_page_color(page)
        replacements_to_apply = []
        
        # 1. Redact Text
        page_height = page.rect.y1 - page.rect.y0
        header_height = page_height * 0.20
        
        # Redact Header/Global Text Blocks (Contact & Address)
        office_anchors = []
        postcode_anchors = []
        for block in page.get_text("blocks"):
            bx0, by0, bx1, by1, btext, bno, btype = block
            if btype == 0:
                text_lower = btext.lower()
                if any(k in text_lower for k in ["head office", "london office", "registered office", "office address"]):
                    office_anchors.append(fitz.Rect(bx0, by0, bx1, by1))
                if POSTAL_CODE_PATTERN.search(btext):
                    postcode_anchors.append(fitz.Rect(bx0, by0, bx1, by1))

        for block in page.get_text("blocks"):
            x0, y0, x1, y1, block_text, block_no, block_type = block
            if block_type == 0:  # text block
                y_center = (y0 + y1) / 2.0
                is_contact = any(k in block_text.lower() for k in ["www", "http", "email", "@", "telephone", "tel", "fax", "contact"])
                has_postcode = bool(POSTAL_CODE_PATTERN.search(block_text))
                has_keyword = any(k in block_text.lower() for k in ["street", "road", "avenue", "lane", "drive", "building", "house", "campus", "centre", "center", "park", "office", "gate"])
                is_multiline = "\n" in block_text.strip()
                
                is_address = has_postcode and (has_keyword or is_multiline)
                
                is_in_office_zone = False
                for anchor in office_anchors:
                    zone = fitz.Rect(anchor.x0 - 80, anchor.y1, anchor.x1 + 80, anchor.y1 + 140)
                    if zone.intersects(fitz.Rect(x0, y0, x1, y1)):
                        is_in_office_zone = True
                        break
                        
                is_in_postcode_zone = False
                for anchor in postcode_anchors:
                    zone = fitz.Rect(anchor.x0 - 80, anchor.y0 - 140, anchor.x1 + 80, anchor.y0)
                    if zone.intersects(fitz.Rect(x0, y0, x1, y1)):
                        is_in_postcode_zone = True
                        break
                
                has_explicit_office = any(k in block_text.lower() for k in ["head office", "london office", "registered office", "office address"])
                is_header_footer_contact = is_contact and (y_center < header_height or y_center > page_height * 0.80)
                
                is_keyword_match = any(k in block_text.lower() for k in ["street", "road", "avenue", "lane", "drive", "building", "house", "campus", "centre", "center", "park", "office", "gate", "london", "nottingham", "manchester", "oxford", "bucks", "leeds", "birmingham", "tel", "phone", "email", "@", "www", "http", "contact"]) or has_postcode
                
                is_valid_address = is_address or has_explicit_office or ((is_in_office_zone or is_in_postcode_zone) and is_keyword_match)
                
                if is_header_footer_contact or is_valid_address:
                    rect = fitz.Rect(x0, y0, x1, y1)
                    padded_rect = padded_redaction_rect(page, rect)
                    local_bg = detect_local_bg_color(page, padded_rect, page_pix)
                    page.add_redact_annot(padded_rect, fill=local_bg)
                    
                    cls = "CONTACT_BLOCK" if is_header_footer_contact else "ADDRESS_BLOCK"
                    # Audit log header block redaction
                    try:
                        from redaction.redaction_audit import RedactionAudit
                        RedactionAudit.log({
                            "candidate": block_text.strip(),
                            "stage": "HEADER_REDACTION",
                            "classification": cls,
                            "decision": "REDACT",
                            "page": page_num + 1,
                            "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                            "bbox_width": round(x1 - x0, 2),
                            "bbox_height": round(y1 - y0, 2)
                        })
                    except Exception:
                        pass

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
                
        # Extract and redact all dates and times using the new detector
        from redaction.date_time_detector import find_date_time_spans
        for start, end, matched_str, m_type in find_date_time_spans(normalized_text):
            matched_str = matched_str.strip()
            if matched_str and len(matched_str) > 2:
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
            # Check if matched_str belongs to active issuing university patterns or contains qualifi
            is_uni_branding = False
            for pattern in get_active_patterns():
                if pattern.search(matched_str):
                    is_uni_branding = True
                    break
            # Also check explicit qualifi/qualify
            if "qualifi" in matched_str.lower() or "qualify" in matched_str.lower():
                is_uni_branding = True

            # Infer classification and source detector
            _src = ""
            if STUDENT_ID_PATTERN.fullmatch(matched_str.strip()):
                _cls, _act = "STUDENT_ID", "REDACT"
            elif EMAIL_PATTERN.search(matched_str):
                _cls, _act = "EMAIL", "REDACT"
            elif PHONE_PATTERN.fullmatch(matched_str.strip()):
                _cls, _act = "PHONE", "REDACT"
            elif is_uni_branding:
                _cls, _act = "UNIVERSITY_BRANDING", "REDACT"
            else:
                if NAME_PROXIMITY_PATTERN.search(matched_str):
                    _src = "PERSON_PATTERN"
                elif SUBMISSION_LOCATION_PATTERN.search(matched_str) or METADATA_FIELD_PATTERN.search(matched_str):
                    _src = "METADATA_FIELD_PATTERN"
                else:
                    from redaction.date_time_detector import find_date_time_spans
                    spans = find_date_time_spans(matched_str)
                    if spans:
                        _, _, _, m_type = spans[0]
                        _src = "DATE_CANDIDATE_PATTERN" if m_type == "DATE" else "TIME_VAL_PATTERN"
                
                from redaction.entity_classifier import classify_entity
                context_win = normalized_text
                if _src == "DATE_CANDIDATE_PATTERN":
                    idx = normalized_text.find(matched_str)
                    if idx != -1:
                        context_win = normalized_text[max(0, idx - 120):min(len(normalized_text), idx + len(matched_str) + 120)]
                _cls, _act, _reasons, _score = classify_entity(
                    matched_str, 
                    context=context_win,
                    source_detector=_src
                )
                
            if _act == "KEEP":
                continue
 
            rects = get_text_match_rects(page, matched_str)
            if not rects:
                rects = page.search_for(matched_str)
            for rect in rects:
                padded_rect = padded_redaction_rect(page, rect)
                               
                _log_pdf(matched_str, _cls, page_num + 1, padded_rect, normalized_text[:500])
                
                local_bg = detect_local_bg_color(page, padded_rect, page_pix)
                page.add_redact_annot(padded_rect, text=replacement, fill=local_bg)
  
                # Phase 7 Log: Final Decision
                try:
                    from redaction.redaction_audit import RedactionAudit
                    RedactionAudit.log({
                        "candidate": matched_str,
                        "stage": "FINAL_DECISION",
                        "classification": _cls,
                        "decision": _act,
                        "decision_source": _cls + "_RULE"
                    })
                except Exception:
                    pass
 
                # Phase 8 Log: Redaction Geometry
                try:
                    from redaction.redaction_audit import RedactionAudit
                    bbox = [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
                    bbox_width = round(rect.x1 - rect.x0, 2)
                    bbox_height = round(rect.y1 - rect.y0, 2)
                    RedactionAudit.log({
                        "candidate": matched_str,
                        "page": page_num + 1,
                        "stage": "REDACTION_GEOMETRY",
                        "bbox": bbox,
                        "bbox_width": bbox_width,
                        "bbox_height": bbox_height,
                        "ocr_text_inside_bbox": matched_str
                    })
                except Exception:
                    pass
 
        # Blank out date/location table value cells geometrically
        redact_pdf_table_rows(page, page_bg_color)
 
        # 2. Redact Hyperlinks
        links = page.get_links()
        for link in links:
            uri = link.get("uri", "")
            if uri:
                # Check if URI matches any patterns
                should_redact_link = False
                if "qualifi" in uri.lower() or "qualify" in uri.lower():
                    should_redact_link = True
                else:
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
                    # Visually redact the hyperlink text
                    rect = link.get("from")
                    if rect:
                        padded_rect = padded_redaction_rect(page, rect)
                        local_bg = detect_local_bg_color(page, padded_rect, page_pix)
                        page.add_redact_annot(padded_rect, fill=local_bg)
 
        # 3. Redact Logos/Images
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img_hash = hash(image_bytes)
                
                # Check if it is inside the header zone
                rects = page.get_image_rects(xref)
                is_header_image = False
                for rect in rects:
                    y_center = (rect.y0 + rect.y1) / 2.0
                    if y_center < header_height:
                        is_header_image = True
                        break
                
                if is_header_image or img_hash in images_to_redact:
                    # Get all rects where this image is placed on the page
                    rects = page.get_image_rects(xref)
                    for rect in rects:
                        # Redact the image location by overlaying a page-colored box
                        local_bg = detect_local_bg_color(page, rect, page_pix)
                        page.add_redact_annot(rect, fill=local_bg)
                        
                        # Log it
                        _log_pdf(f"[IMAGE xref={xref}]", "HEADER_IMAGE" if is_header_image else "UNIVERSITY_BRANDING", page_num + 1, rect)
                        
                        # Log header image to audit summary
                        try:
                            from redaction.redaction_audit import RedactionAudit
                            RedactionAudit.log({
                                "candidate": f"[IMAGE xref={xref}]",
                                "stage": "HEADER_REDACTION" if is_header_image else "FINAL_DECISION",
                                "classification": "HEADER_IMAGE" if is_header_image else "UNIVERSITY_BRANDING",
                                "decision": "REDACT",
                                "page": page_num + 1,
                                "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                                "bbox_width": round(rect.x1 - rect.x0, 2),
                                "bbox_height": round(rect.y1 - rect.y0, 2)
                            })
                        except Exception:
                            pass
                else:
                    # Partial / word-level redaction inside the screenshot/image
                    if 'image_ocr_results' in locals() and img_hash in image_ocr_results:
                        res = image_ocr_results[img_hash]
                        char_mapper = res["char_mapper"]
                        ocr_text = res["ocr_text"]
                        if char_mapper and ocr_text.strip():
                            # Find all matches in ocr_text
                            all_matches = []
                            patterns = [
                                (STUDENT_ID_PATTERN, "STUDENT_ID"),
                                (EMAIL_PATTERN, "EMAIL"),
                                (PHONE_PATTERN, "PHONE"),
                                (POSTAL_CODE_PATTERN, "POSTAL_CODE"),
                            ]
                            for pattern, classification in patterns:
                                for m in pattern.finditer(ocr_text):
                                    all_matches.append((m.start(), m.end(), m.group(0), classification))
                                    
                            for m in NAME_PROXIMITY_PATTERN.finditer(ocr_text):
                                name_str = m.group(1)
                                if is_likely_human_name(name_str, context=m.group(0)):
                                    all_matches.append((m.start(1), m.end(1), name_str, "PERSON"))
                                    
                            # Determine image coordinates for each match
                            rects = page.get_image_rects(xref)
                            for rect in rects:
                                pw = rect.x1 - rect.x0
                                ph = rect.y1 - rect.y0
                                try:
                                    from PIL import Image
                                    import io
                                    pil_img = Image.open(io.BytesIO(base_image["image"]))
                                    iw_px, ih_px = pil_img.size
                                except Exception:
                                    continue
                                    
                                x_scale = pw / iw_px
                                y_scale = ph / ih_px
                                
                                for start, end, match_text, classification in all_matches:
                                    sub_bbox = char_mapper.get_bbox_for_span(start, end)
                                    if sub_bbox:
                                        ix, iy, iw, ih = sub_bbox
                                        page_x0 = rect.x0 + ix * x_scale
                                        page_y0 = rect.y0 + iy * y_scale
                                        page_x1 = page_x0 + iw * x_scale
                                        page_y1 = page_y0 + ih * y_scale
                                        
                                        sub_rect = fitz.Rect(page_x0, page_y0, page_x1, page_y1)
                                        
                                        # Apply padding
                                        from image_processing.redaction_padding import get_adaptive_padding
                                        padded_sub_bbox = get_adaptive_padding([page_x0, page_y0, page_x1 - page_x0, page_y1 - page_y0])
                                        padded_sub_rect = fitz.Rect(padded_sub_bbox[0], padded_sub_bbox[1], padded_sub_bbox[0] + padded_sub_bbox[2], padded_sub_bbox[1] + padded_sub_bbox[3])
                                        padded_sub_rect = padded_sub_rect & page.rect
                                        
                                        # Sample background color
                                        from image_processing.background_sampler import sample_local_background
                                        local_bg = sample_local_background(pil_img, sub_bbox)
                                        local_bg_float = (local_bg[0]/255.0, local_bg[1]/255.0, local_bg[2]/255.0)
                                        
                                        page.add_redact_annot(padded_sub_rect, fill=local_bg_float)
                                        
                                        # Log the sub-redaction
                                        from redaction.redaction_audit import RedactionAudit
                                        RedactionAudit.log({
                                            "candidate": match_text,
                                            "stage": "FINAL_DECISION",
                                            "classification": classification,
                                            "decision": "REDACT",
                                            "background_sampled": True,
                                            "adaptive_padding": True
                                        })
 
                        # Phase 7 Log: Final Decision
                        try:
                            from redaction.redaction_audit import RedactionAudit
                            RedactionAudit.log({
                                "candidate": f"[IMAGE xref={xref}]",
                                "stage": "FINAL_DECISION",
                                "classification": "UNIVERSITY_BRANDING",
                                "decision": "REDACT",
                                "decision_source": "UNIVERSITY_BRANDING"
                            })
                        except Exception:
                            pass
 
                        # Phase 8 Log: Redaction Geometry
                        try:
                            from redaction.redaction_audit import RedactionAudit
                            bbox = [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
                            bbox_width = round(rect.x1 - rect.x0, 2)
                            bbox_height = round(rect.y1 - rect.y0, 2)
                            RedactionAudit.log({
                                "candidate": f"[IMAGE xref={xref}]",
                                "page": page_num + 1,
                                "stage": "REDACTION_GEOMETRY",
                                "bbox": bbox,
                                "bbox_width": bbox_width,
                                "bbox_height": bbox_height,
                                "ocr_text_inside_bbox": f"[IMAGE xref={xref}]"
                            })
                        except Exception:
                            pass
            except Exception:
                pass
                
        # Apply all redactions on this page
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
        
    doc.save(output_path, garbage=3, deflate=True)
    doc.close()

    # Write final audit summary report at the very end
    try:
        from redaction.redaction_audit import RedactionAudit
        from redaction.escalation_manager import LOGS_DIR
        summary = RedactionAudit.generate_summary(doc_id)
        summary_file = os.path.join(LOGS_DIR, "audit_summary.json")
        with open(summary_file, "w", encoding="utf-8") as sf:
            json.dump(summary, sf, indent=2)
    except Exception as re_err:
        print(f"Error generating final redaction audit report: {re_err}")

