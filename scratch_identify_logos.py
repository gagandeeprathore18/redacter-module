import easyocr
import os

logos_dir = "/home/user/drafter-module/logos"
reader = easyocr.Reader(['en'], gpu=False)

for filename in os.listdir(logos_dir):
    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        continue
    logo_path = os.path.join(logos_dir, filename)
    res = reader.readtext(logo_path)
    texts = [item[1] for item in res]
    print(f"Template: {filename} | OCR Text: {texts}")
