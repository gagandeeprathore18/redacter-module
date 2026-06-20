import io
from PIL import Image
from image_processing.image_ocr_mapper import ImageOCRMapper
from image_processing.image_char_mapper import ImageCharMapper
from image_processing.screenshot_detector import detect_screenshot_ui
from image_processing.image_branding_detector import detect_image_branding

def process_raster_image(image_bytes: bytes, location: str = "") -> dict:
    """
    Enhanced image processing pipeline.
    Takes image_bytes, runs screenshot UI detection, crops if necessary,
    runs OCR mapping, constructs character maps, detects header/footer branding,
    and returns a dict of results (ocr_text, ocr_words, char_mapper, cropped_image, etc.).
    """
    # 1. Load image
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
    except Exception:
        return {
            "ocr_text": "",
            "ocr_words": [],
            "char_mapper": None,
            "cropped_image": None,
            "screenshot_ui_detected": False,
            "crop_top": 0,
            "crop_bottom": 0,
            "ocr_words_detected": 0,
            "char_map_entries": 0
        }
        
    # 2. Run initial OCR to detect UI
    ocr_mapper = ImageOCRMapper()
    initial_words = ocr_mapper.get_ocr_words(image_bytes)
    ocr_words_detected = len(initial_words)
    
    # 3. Screenshot UI detection and cropping
    crop_top, crop_bottom = detect_screenshot_ui(initial_words, width, height)
    screenshot_ui_detected = (crop_top > 0 or crop_bottom < height)
    
    cropped_img = pil_img
    y_offset = 0
    if screenshot_ui_detected:
        cropped_img = pil_img.crop((0, crop_top, width, crop_bottom))
        y_offset = crop_top
        
        # Save cropped image to bytes to re-run OCR
        try:
            cropped_bytes_io = io.BytesIO()
            fmt = pil_img.format if pil_img.format else "PNG"
            cropped_img.save(cropped_bytes_io, format=fmt)
            cropped_bytes = cropped_bytes_io.getvalue()
            final_words = ocr_mapper.get_ocr_words(cropped_bytes)
            
            # Offset vertical coordinates back to original image space
            for word in final_words:
                word.bbox[1] += y_offset
        except Exception:
            final_words = initial_words
    else:
        final_words = initial_words
        
    # 4. Header/Footer branding detection
    detect_image_branding(final_words, height)
    
    # 5. Character mapping
    char_mapper = ImageCharMapper(final_words)
    
    return {
        "ocr_text": char_mapper.full_text,
        "ocr_words": final_words,
        "char_mapper": char_mapper,
        "cropped_image": cropped_img,
        "screenshot_ui_detected": screenshot_ui_detected,
        "crop_top": crop_top,
        "crop_bottom": crop_bottom,
        "ocr_words_detected": ocr_words_detected,
        "char_map_entries": len(char_mapper.char_map)
    }
