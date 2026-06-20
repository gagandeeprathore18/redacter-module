import easyocr
import cv2

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781953052814.png"
img = cv2.imread(image_path)

# Upscale by 2x
height, width = img.shape[:2]
img_large = cv2.resize(img, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

# Save large image temporarily
cv2.imwrite("temp_large.png", img_large)

reader = easyocr.Reader(['en'], gpu=False)
results = reader.readtext("temp_large.png")

print("=== EasyOCR Upscaled Results ===")
for bbox_pts, text, confidence in results:
    if confidence > 0.15:
        # Scale bbox back to original size for inspection
        orig_pts = [[int(pt[0]/2), int(pt[1]/2)] for pt in bbox_pts]
        print(f"Text={repr(text)} conf={confidence:.4f} bbox={orig_pts}")
