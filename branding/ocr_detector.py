import easyocr
import io

class OCRDetector:
    def __init__(self):
        # Initialize reader. 'en' for English language.
        # gpu=False ensures it runs reliably on standard CPUs locally.
        self.reader = easyocr.Reader(['en'], gpu=False)
        
    def extract_text(self, image_bytes: bytes) -> str:
        """
        Runs EasyOCR on preprocessed image bytes and returns a normalized lowercase string.
        """
        try:
            # Check if PIL can open it and if it's a vector format (EMF, WMF)
            from PIL import Image
            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    if img.format in ('EMF', 'WMF'):
                        return ""
            except Exception:
                return ""

            # EasyOCR can read from a byte stream directly
            results = self.reader.readtext(image_bytes)
            
            # Extract text elements and join them
            text_lines = []
            for bbox, text, confidence in results:
                # Filter out extremely low confidence results to prevent noise
                if confidence > 0.2:
                    text_lines.append(text.strip().lower())
                    
            normalized_text = " ".join(text_lines)
            return normalized_text
        except Exception as e:
            print(f"Error during OCR detection: {e}")
            return ""
