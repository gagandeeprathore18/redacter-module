from redaction.ownership_manager import register_detected_university, extract_institution_names_from_text

def detect_image_branding(ocr_words: list, img_height: float):
    """
    Scans the top 15% and bottom 15% of the image for branding/institution text.
    If detected, registers the names using ownership_manager.
    """
    top_limit = img_height * 0.15
    bottom_limit = img_height * 0.85
    
    zone_words = []
    for word in ocr_words:
        x, y, w, h = word.bbox
        y_center = y + h / 2.0
        if y_center < top_limit or y_center > bottom_limit:
            zone_words.append(word.text)
            
    if not zone_words:
        return
        
    combined_text = " ".join(zone_words)
    extracted_names = extract_institution_names_from_text(combined_text)
    for name in extracted_names:
        register_detected_university(name)
        print(f"Branding detector registered header/footer entity: {name}")
