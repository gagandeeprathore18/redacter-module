import os
import io
import json
import re
from PIL import Image, ImageDraw, ImageFont
from image_processing.pipeline import process_raster_image
from image_processing.redaction_padding import get_adaptive_padding
from image_processing.background_sampler import sample_local_background
from redaction.entity_classifier import classify_entity
from redaction.redaction_audit import RedactionAudit
from redact_engine import (
    STUDENT_ID_PATTERN, EMAIL_PATTERN, PHONE_PATTERN, POSTAL_CODE_PATTERN,
    NAME_PROXIMITY_PATTERN, NAME_PATTERN, URL_OR_DOMAIN_PATTERN, is_likely_human_name
)

FUZZY_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\b')

def process_image(input_path: str, output_path: str):
    """
    Direct Image Redactor.
    Loads the image, runs screenshot/OCR processing, extracts/classifies candidates,
    renders redactions directly on the image canvas, crops UI, and saves it.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input image path '{input_path}' does not exist.")

    # Set document ID for auditing
    os.environ["CURRENT_DOCUMENT_ID"] = os.path.basename(input_path)

    # 1. Load image bytes
    with open(input_path, "rb") as f:
        image_bytes = f.read()

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
        img_format = pil_img.format or "PNG"
    except Exception as err:
        raise ValueError(f"Could not open image via PIL: {err}")

    # 2. Run advanced image processing pipeline
    res = process_raster_image(image_bytes, "body")
    char_mapper = res["char_mapper"]
    ocr_text = res["ocr_text"]

    # Log document processing metrics
    RedactionAudit.log({
        "candidate": f"[IMAGE document={os.path.basename(input_path)}]",
        "stage": "IMAGE_PRE_PROCESSING",
        "classification": "IMAGE",
        "decision": "KEEP",
        "ocr_words_detected": res["ocr_words_detected"],
        "char_map_entries": res["char_map_entries"],
        "screenshot_ui_detected": res["screenshot_ui_detected"],
        "screenshot_ui_cropped": 1 if res["screenshot_ui_detected"] else 0,
        "image_documents_processed": 1
    })

    if not char_mapper or not ocr_text.strip():
        # Save cropped or original image if no text
        final_img = res["cropped_image"] if res["screenshot_ui_detected"] else pil_img
        final_img.save(output_path, format=img_format)
        return

    # 3. Find candidates and run classification
    from redaction.ownership_manager import determine_issuing_university, scan_text_for_universities, get_active_patterns
    from redaction.date_time_detector import find_date_time_spans
    determine_issuing_university(ocr_text)
    scan_text_for_universities(ocr_text)

    all_matches = []
    
    # 3.1 Date / Time Spans
    for start, end, matched_str, m_type in find_date_time_spans(ocr_text):
        classification = "DATE_CANDIDATE" if m_type == "DATE" else "TIME_VALUE"
        source_det = "DATE_CANDIDATE_PATTERN" if m_type == "DATE" else "TIME_VAL_PATTERN"
        all_matches.append((start, end, matched_str, classification, source_det))

    # 3.2 Standard Patterns
    patterns = [
        (STUDENT_ID_PATTERN, "STUDENT_ID", "STUDENT_ID_PATTERN"),
        (EMAIL_PATTERN, "EMAIL", "EMAIL_PATTERN"),
        (FUZZY_EMAIL_PATTERN, "EMAIL", "EMAIL_PATTERN"),
        (PHONE_PATTERN, "PHONE", "PHONE_PATTERN"),
        (POSTAL_CODE_PATTERN, "POSTAL_CODE", "POSTAL_CODE_PATTERN"),
        (URL_OR_DOMAIN_PATTERN, "URL_OR_DOMAIN", "URL_OR_DOMAIN_PATTERN"),
    ]
    for pattern, classification, source_det in patterns:
        for m in pattern.finditer(ocr_text):
            match_str = m.group(0)
            if not any(match_str in x[2] for x in all_matches):
                all_matches.append((m.start(), m.end(), match_str, classification, source_det))

    # 3.3 Active University Patterns
    for pattern in get_active_patterns():
        for m in pattern.finditer(ocr_text):
            match_str = m.group(0)
            if not any(match_str in x[2] for x in all_matches):
                all_matches.append((m.start(), m.end(), match_str, "UNIVERSITY_BRANDING", "UNIVERSITY_BRANDING"))

    # Robust Substring University Matching (handles OCR merges/misreadings, lookalikes, and letter-spacing)
    from redaction.ownership_manager import get_issuing_university, get_issuing_aliases
    
    def make_spacing_lookalike_regex(text: str) -> re.Pattern:
        char_groups = {
            'a': '[a4]', 'b': '[b8]', 'c': '[c€]', 'd': '[d0o]', 'e': '[e]', 'f': '[f]', 'g': '[g]',
            'h': '[hk]', 'i': '[i|1l]', 'j': '[j]', 'k': '[kh]', 'l': '[l1|\[]', 'm': '[m]', 'n': '[n]',
            'o': '[o0d]', 'p': '[p]', 'q': '[q]', 'r': '[r]', 's': '[s5\$]', 't': '[t]', 'u': '[u]',
            'v': '[v]', 'w': '[w]', 'x': '[x]', 'y': '[y]', 'z': '[z]',
        }
        parts = []
        for c in text.lower():
            if c.isalnum():
                parts.append(char_groups.get(c, c))
        regex_str = r"\s*".join(parts)
        return re.compile(regex_str, re.IGNORECASE)
        
    uni_name = get_issuing_university()
    aliases = get_issuing_aliases()
    sub_patterns = []
    if uni_name:
        sub_patterns.append(uni_name)
    if uni_name and "global banking" in uni_name.lower():
        sub_patterns.append("globalbanking")
    for alias in aliases:
        if len(alias) > 3:
            sub_patterns.append(alias)
            
    for pat in sub_patterns:
        pattern_regex = make_spacing_lookalike_regex(pat)
        for m in pattern_regex.finditer(ocr_text):
            start, end = m.start(), m.end()
            # Expand to boundaries
            while start > 0 and (ocr_text[start - 1].isalnum() or ocr_text[start - 1] in '@._- '):
                if ocr_text[start - 1] == ' ' and (start < 2 or not ocr_text[start - 2].isalnum()):
                    break
                start -= 1
            while end < len(ocr_text) and (ocr_text[end].isalnum() or ocr_text[end] in '@._- '):
                if ocr_text[end] == ' ' and (end > len(ocr_text) - 2 or not ocr_text[end + 1].isalnum()):
                    break
                end += 1
            expanded_str = ocr_text[start:end].strip()
            if not any(expanded_str in x[2] for x in all_matches):
                all_matches.append((start, end, expanded_str, "UNIVERSITY_BRANDING", "UNIVERSITY_BRANDING"))

    # Redact common university descriptor keywords only in the header/footer zones (top/bottom 15%)
    common_descriptors = ["business", "school", "university", "college", "academy", "institute"]
    for pat in common_descriptors:
        pattern_regex = make_spacing_lookalike_regex(pat)
        for m in pattern_regex.finditer(ocr_text):
            sub_bbox = char_mapper.get_bbox_for_span(m.start(), m.end())
            if sub_bbox:
                y = sub_bbox[1]
                if y < pil_img.height * 0.15 or y > pil_img.height * 0.85:
                    start, end = m.start(), m.end()
                    while start > 0 and (ocr_text[start - 1].isalnum() or ocr_text[start - 1] in '@._- '):
                        if ocr_text[start - 1] == ' ' and (start < 2 or not ocr_text[start - 2].isalnum()):
                            break
                        start -= 1
                    while end < len(ocr_text) and (ocr_text[end].isalnum() or ocr_text[end] in '@._- '):
                        if ocr_text[end] == ' ' and (end > len(ocr_text) - 2 or not ocr_text[end + 1].isalnum()):
                            break
                        end += 1
                    expanded_str = ocr_text[start:end].strip()
                    if not any(expanded_str in x[2] for x in all_matches):
                        all_matches.append((start, end, expanded_str, "UNIVERSITY_BRANDING", "UNIVERSITY_BRANDING"))

    # 3.4 Name matching (with proximity and standalone patterns)
    for m in NAME_PROXIMITY_PATTERN.finditer(ocr_text):
        name_str = m.group(1)
        if is_likely_human_name(name_str, context=m.group(0)):
            if not any(name_str in x[2] for x in all_matches):
                all_matches.append((m.start(1), m.end(1), name_str, "PERSON", ""))

    for m in NAME_PATTERN.finditer(ocr_text):
        name_str = m.group(0)
        # Avoid duplicating existing matches
        if not any(name_str in x[2] for x in all_matches):
            if is_likely_human_name(name_str, context=ocr_text):
                all_matches.append((m.start(), m.end(), name_str, "PERSON", ""))

    # 4. Render redactions
    draw = ImageDraw.Draw(pil_img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    redactions_applied = 0
    for start, end, match_text, classification, source_detector in all_matches:
        # Classifier decision (can be KEEP, REDACT, or REPLACE)
        # Reuses existing classify_entity logic
        cls, action, reasons, score = classify_entity(
            match_text, context=ocr_text, source_detector=source_detector
        )
        
        if action == "KEEP":
            continue
            
        sub_bbox = char_mapper.get_bbox_for_span(start, end)
        if sub_bbox:
            # Apply dynamic adaptive padding
            padded_bbox = get_adaptive_padding(sub_bbox, pil_img.size)
            px, py, pw, ph = padded_bbox
            
            # Sample local background color
            local_bg = sample_local_background(pil_img, sub_bbox)
            
            # Draw redaction box
            draw.rectangle([px, py, px + pw, py + ph], fill=local_bg)
            
            if action == "REPLACE" or cls in ("UNIVERSITY_ENTITY", "UNIVERSITY_BRANDING"):
                # Render replacement text (e.g. for UNIVERSITY_BRANDING)
                text_color = (0, 0, 0) if sum(local_bg) > 382 else (255, 255, 255)
                # Compute a nice vertical/horizontal offset or align
                draw.text((px + 2, py + 2), "University", fill=text_color, font=font)
                
            redactions_applied += 1
            
            # Log final audit event
            RedactionAudit.log({
                "candidate": match_text,
                "stage": "FINAL_DECISION",
                "classification": cls,
                "decision": action,
                "background_sampled": True,
                "adaptive_padding": True,
                "image_redactions_applied": 1
            })

    # 4.1 Run Logo template matching (for visual logos in flat images)
    try:
        import cv2
        import numpy as np
        # Convert PIL Image to OpenCV BGR image
        open_cv_image = np.array(pil_img)
        img_bgr = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        logos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos")
        if not os.path.exists(logos_dir):
            logos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logos")
            
        if os.path.exists(logos_dir):
            for filename in os.listdir(logos_dir):
                if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
                logo_path = os.path.join(logos_dir, filename)
                logo_bgr = cv2.imread(logo_path)
                if logo_bgr is None:
                    continue
                logo_gray = cv2.cvtColor(logo_bgr, cv2.COLOR_BGR2GRAY)
                
                h_temp, w_temp = logo_gray.shape[:2]
                best_val = 0
                best_loc = None
                best_scale = 1.0
                
                # Check match across multiple scales
                for scale in np.linspace(0.15, 1.5, 25):
                    resized_w = int(w_temp * scale)
                    resized_h = int(h_temp * scale)
                    
                    if resized_w > img_gray.shape[1] or resized_h > img_gray.shape[0]:
                        continue
                    if resized_w < 15 or resized_h < 15:
                        continue
                        
                    resized_logo = cv2.resize(logo_gray, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
                    res_match = cv2.matchTemplate(img_gray, resized_logo, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res_match)
                    
                    if max_val > best_val:
                        best_val = max_val
                        best_loc = max_loc
                        best_scale = scale
                        
                # Threshold for a match: 0.65
                if best_val > 0.65:
                    rx, ry = best_loc
                    rw = int(w_temp * best_scale)
                    rh = int(h_temp * best_scale)
                    
                    logo_bbox = [rx, ry, rw, rh]
                    local_bg = sample_local_background(pil_img, logo_bbox)
                    padded_bbox = get_adaptive_padding(logo_bbox, pil_img.size)
                    px, py, pw, ph = padded_bbox
                    
                    draw.rectangle([px, py, px + pw, py + ph], fill=local_bg)
                    redactions_applied += 1
                    
                    RedactionAudit.log({
                        "candidate": f"[LOGO matched template={filename}]",
                        "stage": "FINAL_DECISION",
                        "classification": "UNIVERSITY_BRANDING",
                        "decision": "REDACT",
                        "background_sampled": True,
                        "adaptive_padding": True,
                        "image_redactions_applied": 1
                    })
                    print(f"OpenCV template matched logo: {filename} with score {best_val:.3f}")
    except Exception as cv_err:
        print(f"OpenCV logo template matching skipped/failed: {cv_err}")

    # 5. Crop screenshot UI elements if detected and save final
    final_img = pil_img
    if res["screenshot_ui_detected"]:
        crop_top = res["crop_top"]
        crop_bottom = res["crop_bottom"]
        final_img = pil_img.crop((0, crop_top, width, crop_bottom))
        
    final_img.save(output_path, format=img_format)
    print(f"Direct image redaction finished. Applied {redactions_applied} redactions.")
