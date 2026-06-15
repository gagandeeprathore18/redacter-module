import cv2
import numpy as np
from PIL import Image
import io

def preprocess_image(image_bytes: bytes) -> bytes:
    """
    Applies image preprocessing: grayscale, thresholding, and noise reduction
    to optimize text recognition for OCR.
    """
    try:
        # Load image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Resize if too small (upscaling helps OCR)
        h, w = gray.shape[:2]
        if h < 200 or w < 200:
            gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            
        # Denoise
        denoised = cv2.medianBlur(gray, 3)
        
        # Adaptive Thresholding / Otsu Thresholding
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Encode back to PNG bytes
        _, buffer = cv2.imencode('.png', thresh)
        return buffer.tobytes()
    except Exception as e:
        print(f"Error preprocessing image: {e}")
        return image_bytes
