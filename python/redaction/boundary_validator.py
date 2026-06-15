import re
from redaction.heading_boundary_detector import is_section_boundary
from redaction.protected_section_detector import is_protected_section

def should_stop_expansion(
    text: str,
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False,
    is_table_header: bool = False
) -> bool:
    """
    Enforces boundary expansion validation.
    Returns True if expansion must stop immediately.
    """
    if not text:
        return False
        
    cleaned = text.strip()
    if not cleaned:
        return False
        
    # Stop on protected sections
    if is_protected_section(cleaned):
        return True
        
    # Stop on heading boundaries
    if is_section_boundary(cleaned, is_bold=is_bold, font_size=font_size, is_standalone=is_standalone, is_table_header=is_table_header):
        return True
        
    # Stop on section separators / horizontal dividers
    if re.match(r'^[_\-\*\s]{3,}$', cleaned):
        return True
        
    return False
