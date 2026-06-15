from PIL import Image
import io

def remove_logo_inplace(img_meta: dict) -> None:
    """
    Overwrites the image binary content in the DOCX package with a 1x1 transparent PNG.
    This preserves the layout while making the logo invisible.
    """
    try:
        # Generate a 1x1 transparent PNG
        img = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blank_bytes = buf.getvalue()
        
        # Replace the part's binary blob in-place
        part = img_meta.get("part")
        if part:
            part._blob = blank_bytes
            print(f"Successfully removed logo image {img_meta.get('rId')} in-place.")
    except Exception as e:
        print(f"Error removing logo in-place: {e}")
