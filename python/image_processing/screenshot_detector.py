import re

def detect_screenshot_ui(ocr_words: list, img_width: int, img_height: int) -> tuple:
    """
    Detects browser/mobile UI elements in the top 15% and bottom 15% of the image.
    Returns (crop_top, crop_bottom) coordinates. If no UI is found, returns (0, img_height).
    """
    has_strong_top_ui = False
    has_strong_bottom_ui = False
    top_ui_elements_y = []
    bottom_ui_elements_y = []
    
    # Strict regex patterns for UI detection (allowing spaces as dot-substitutes from OCR)
    strict_url_pattern = r"(?i)^(?:https?://)?[a-z0-9\-]+(?:[\.\s][a-z0-9\-]+)+\.[a-z]{2,6}/?$"
    strict_time_pattern = r"^\d{1,2}:\d{2}$"
    strict_battery_pattern = r"^\d{1,3}%$"
    
    phone_ui_patterns = [
        r"(?i)\b(?:https?://)?[a-z0-9\-]+(?:[\.\s][a-z0-9\-]+)+\.[a-z]{2,6}\b",
        r"\b\d{1,2}:\d{2}\b",
        r"\b\d{1,3}%\b"
    ]
    
    top_zone = img_height * 0.15
    bottom_zone = img_height * 0.85
    
    for word in ocr_words:
        text = word.text.strip()
        if not text:
            continue
            
        x, y, w, h = word.bbox
        
        # Check Top UI (Strictly top 15%)
        if y < top_zone:
            if re.match(strict_battery_pattern, text) and y < img_height * 0.08:
                has_strong_top_ui = True
            elif re.match(strict_url_pattern, text):
                has_strong_top_ui = True
            elif re.match(strict_time_pattern, text) and y < img_height * 0.08:
                has_strong_top_ui = True
                
            for p in phone_ui_patterns:
                if re.search(p, text):
                    top_ui_elements_y.append(y + h)
                    break
                    
        # Check Bottom UI (strictly bottom 15%)
        elif y > bottom_zone:
            if re.match(strict_url_pattern, text):
                has_strong_bottom_ui = True
                
            for p in phone_ui_patterns:
                if re.search(p, text):
                    bottom_ui_elements_y.append(y)
                    break
                    
    crop_top = 0
    crop_bottom = img_height
    
    if has_strong_top_ui and top_ui_elements_y:
        max_ui_y = max(top_ui_elements_y)
        crop_top = int(min(max_ui_y + int(img_height * 0.04), int(img_height * 0.25)))
        
    if has_strong_bottom_ui and bottom_ui_elements_y:
        min_ui_y = min(bottom_ui_elements_y)
        crop_bottom = int(max(min_ui_y - 15, int(img_height * 0.75)))
        
    return crop_top, crop_bottom
