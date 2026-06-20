import easyocr
import cv2

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781953052814.png"
reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext(image_path)

print("=== EasyOCR Raw Results ===")
for bbox_pts, text, confidence in results:
    print(f"Text={repr(text)} conf={confidence:.4f} bbox={bbox_pts}")
