import numpy as np
from PIL import Image

def sample_local_background(image: Image.Image, bbox: list, margin: int = 5) -> tuple:
    """
    Samples pixels in a ring immediately outside the bounding box [x, y, w, h]
    in the PIL Image, and returns the median RGB color tuple.
    """
    try:
        width, height = image.size
        x, y, w, h = bbox
        
        # Coordinates of the bbox corners clamped to image boundaries
        rx0 = max(0, min(int(x), width - 1))
        ry0 = max(0, min(int(y), height - 1))
        rx1 = max(0, min(int(x + w), width - 1))
        ry1 = max(0, min(int(y + h), height - 1))
        
        colors = []
        
        # Sample top edge (above the rect)
        sample_y_top = max(0, ry0 - margin)
        for px in range(rx0, rx1 + 1, max(1, (rx1 - rx0) // 8)):
            px = min(px, width - 1)
            color = image.getpixel((px, sample_y_top))
            if isinstance(color, int):
                colors.append((color, color, color))
            else:
                colors.append(color[:3])
            
        # Sample bottom edge (below the rect)
        sample_y_bot = min(height - 1, ry1 + margin)
        for px in range(rx0, rx1 + 1, max(1, (rx1 - rx0) // 8)):
            px = min(px, width - 1)
            color = image.getpixel((px, sample_y_bot))
            if isinstance(color, int):
                colors.append((color, color, color))
            else:
                colors.append(color[:3])
            
        # Sample left edge (left of the rect)
        sample_x_left = max(0, rx0 - margin)
        for py in range(ry0, ry1 + 1, max(1, (ry1 - ry0) // 4)):
            py = min(py, height - 1)
            color = image.getpixel((sample_x_left, py))
            if isinstance(color, int):
                colors.append((color, color, color))
            else:
                colors.append(color[:3])
            
        # Sample right edge (right of the rect)
        sample_x_right = min(width - 1, rx1 + margin)
        for py in range(ry0, ry1 + 1, max(1, (ry1 - ry0) // 4)):
            py = min(py, height - 1)
            color = image.getpixel((sample_x_right, py))
            if isinstance(color, int):
                colors.append((color, color, color))
            else:
                colors.append(color[:3])
            
        # Filter out dark/text pixels
        bg_colors = [c for c in colors if sum(c) > 200]
        if not bg_colors:
            bg_colors = [c for c in colors if sum(c) > 100]
        if not bg_colors:
            bg_colors = colors
            
        if not bg_colors:
            return (255, 255, 255)
            
        # Calculate median RGB values
        arr = np.array(bg_colors)
        median = np.median(arr, axis=0)
        return tuple(int(val) for val in median)
    except Exception as e:
        print(f"Error sampling local background from PIL Image: {e}")
        return (255, 255, 255)
