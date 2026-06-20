import sys
sys.path.insert(0, "/home/user/drafter-module")

from python.image_processing.pipeline import process_raster_image
from python.image_processing.screenshot_detector import detect_screenshot_ui

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781953052814.png"

with open(image_path, "rb") as f:
    image_bytes = f.read()

from PIL import Image
import io
img = Image.open(io.BytesIO(image_bytes))
print(f"Image Size: {img.size}")

res = process_raster_image(image_bytes, "body")
print("\n=== OCR Text ===")
print(res["ocr_text"])

print("\n=== Bboxes of interest ===")
for word in res["ocr_words"]:
    if "lslondon" in word.text.lower() or "harvard" in word.text.lower() or "business" in word.text.lower() or "school" in word.text.lower():
        print(f"Text={repr(word.text)} bbox={word.bbox} conf={word.confidence:.3f}")

print(f"\nScreenshot detected: {res['screenshot_ui_detected']}, crop_top={res['crop_top']}, crop_bottom={res['crop_bottom']}")
