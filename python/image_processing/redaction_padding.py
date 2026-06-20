def get_adaptive_padding(bbox: list, img_size: tuple = None) -> list:
    """
    Intelligently pads the bounding box [x, y, w, h] based on size.
    x_pad = max(2, width * 0.05)
    y_pad = max(2, height * 0.10)
    Returns [padded_x, padded_y, padded_w, padded_h].
    """
    x, y, w, h = bbox
    
    x_pad = max(2.0, w * 0.05)
    y_pad = max(2.0, h * 0.10)
    
    px = x - x_pad
    py = y - y_pad
    pw = w + 2.0 * x_pad
    ph = h + 2.0 * y_pad
    
    if img_size:
        img_w, img_h = img_size
        px_clamped = max(0.0, min(px, img_w - 1.0))
        py_clamped = max(0.0, min(py, img_h - 1.0))
        
        # Adjust width and height based on clamping
        pw_clamped = min(pw - (px_clamped - px), img_w - px_clamped)
        ph_clamped = min(ph - (py_clamped - py), img_h - py_clamped)
        
        return [px_clamped, py_clamped, pw_clamped, ph_clamped]
        
    return [px, py, pw, ph]
