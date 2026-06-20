import easyocr
import io
from PIL import Image

class OCRWord:
    def __init__(self, text: str, bbox: list, confidence: float):
        self.text = text
        self.bbox = bbox  # [x, y, w, h]
        self.confidence = confidence

    def to_dict(self):
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence
        }

class ImageOCRMapper:
    def __init__(self):
        # Reuse English reader, CPU bound for local testing
        self.reader = easyocr.Reader(['en'], gpu=False)

    def get_ocr_words(self, image_bytes: bytes) -> list:
        """
        Runs EasyOCR on preprocessed image bytes and returns a list of OCRWord instances.
        """
        scale = 1
        height = 1000
        try:
            # Check format
            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    if img.format in ('EMF', 'WMF'):
                        return []
                    width, height = img.size
                    
                    # Upscale small images by 2x to improve OCR accuracy
                    if width < 1200 or height < 1200:
                        scale = 2
                        img = img.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
                        
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format=img.format or 'PNG')
                        image_bytes = img_byte_arr.getvalue()
            except Exception:
                return []

            results = self.reader.readtext(image_bytes)
            ocr_words = []
            for bbox_pts, text, confidence in results:
                # Convert EasyOCR 4 corners to [x, y, w, h] and scale back
                xs = [pt[0] for pt in bbox_pts]
                ys = [pt[1] for pt in bbox_pts]
                x = min(xs) / scale
                y = min(ys) / scale
                w = (max(xs) - min(xs)) / scale
                h = (max(ys) - min(ys)) / scale
                
                # Lower threshold for header/footer regions to catch stylized logos/URLs
                # y * scale is the coordinate in the scaled image (which results is in)
                img_h_scaled = height * scale if 'height' in locals() else 1000
                is_header_or_footer = (y * scale < img_h_scaled * 0.15) or (y * scale > img_h_scaled * 0.85)
                threshold = 0.12 if is_header_or_footer else 0.20
                
                if confidence > threshold:
                    ocr_words.append(OCRWord(
                        text=text.strip(),
                        bbox=[x, y, w, h],
                        confidence=float(confidence)
                    ))
            return ocr_words
        except Exception as e:
            print(f"Error during OCR spatial mapping: {e}")
            return []
