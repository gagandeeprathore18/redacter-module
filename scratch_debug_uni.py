import sys
sys.path.insert(0, "/home/user/drafter-module")

from python.image_processing.pipeline import process_raster_image
from python.redaction.ownership_manager import (
    determine_issuing_university, get_issuing_university, get_issuing_aliases,
    get_active_patterns, normalize_lookalikes
)

image_path = "/home/user/.gemini/antigravity-ide/brain/57a89226-cff2-4c7f-977f-eec648b4e1b7/media__1781953052814.png"
with open(image_path, "rb") as f:
    image_bytes = f.read()

res = process_raster_image(image_bytes, "body")
ocr_text = res["ocr_text"]

print(f"Original OCR Text: {repr(ocr_text)}")
print(f"Lookalike normalized OCR text: {repr(normalize_lookalikes(ocr_text))}")

determine_issuing_university(ocr_text)

print(f"Determined University: {get_issuing_university()}")
print(f"Aliases: {get_issuing_aliases()}")
print(f"Active Patterns Count: {len(get_active_patterns())}")
