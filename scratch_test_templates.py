import cv2
import numpy as np
import os

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781953052814.png"
logos_dir = "/home/user/drafter-module/logos"

img_bgr = cv2.imread(image_path)
img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

for filename in os.listdir(logos_dir):
    if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
        continue
    logo_path = os.path.join(logos_dir, filename)
    logo_bgr = cv2.imread(logo_path)
    logo_gray = cv2.cvtColor(logo_bgr, cv2.COLOR_BGR2GRAY)
    
    h_temp, w_temp = logo_gray.shape[:2]
    best_val = 0
    
    for scale in np.linspace(0.15, 1.5, 25):
        resized_w = int(w_temp * scale)
        resized_h = int(h_temp * scale)
        if resized_w > img_gray.shape[1] or resized_h > img_gray.shape[0]:
            continue
        if resized_w < 15 or resized_h < 15:
            continue
        resized_logo = cv2.resize(logo_gray, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        res_match = cv2.matchTemplate(img_gray, resized_logo, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res_match)
        if max_val > best_val:
            best_val = max_val
            
    print(f"Template {filename}: best match score = {best_val:.3f}")
