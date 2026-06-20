import sys
sys.path.insert(0, "/home/user/drafter-module")

from PIL import Image
import numpy as np
import io

from python.image_processing.pipeline import process_raster_image
from python.image_processing.redaction_padding import get_adaptive_padding
from python.image_processing.background_sampler import sample_local_background
from python.redaction.entity_classifier import classify_entity
from python.redaction.date_time_detector import find_date_time_spans

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781952118097.png"
with open(image_path, "rb") as f:
    image_bytes = f.read()

res = process_raster_image(image_bytes, "body")
ocr_text = res["ocr_text"]
char_mapper = res["char_mapper"]

# Find 25/06/2026 span
for start, end, matched_str, m_type in find_date_time_spans(ocr_text):
    if "25/06/2026" in matched_str:
        sub_bbox = char_mapper.get_bbox_for_span(start, end)
        padded_bbox = get_adaptive_padding(sub_bbox, (400, 800)) # dummy size
        print(f"Match: {matched_str}")
        print(f"Span: {start}-{end}")
        print(f"Sub-Bbox: {sub_bbox}")
        print(f"Padded-Bbox: {padded_bbox}")
        
        # Let's read pixel color in original image around sub_bbox
        pil_img = Image.open(io.BytesIO(image_bytes))
        local_bg = sample_local_background(pil_img, sub_bbox)
        print(f"Sampled Local BG: {local_bg}")
        
        # Draw and check pixels
        from PIL import ImageDraw
        draw = ImageDraw.Draw(pil_img)
        px, py, pw, ph = padded_bbox
        draw.rectangle([px, py, px + pw, py + ph], fill=local_bg)
        
        # Get pixels in drawing area
        region = pil_img.crop((px, py, px + pw, py + ph))
        pixels = np.array(region)
        unique_colors = np.unique(pixels.reshape(-1, pixels.shape[-1]), axis=0)
        print(f"Unique colors after draw: {unique_colors}")
