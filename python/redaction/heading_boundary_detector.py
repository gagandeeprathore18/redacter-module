import re
from redaction.heading_detector import is_academic_heading
from redaction.protected_section_detector import is_protected_section

SECTION_KEYWORDS = [
    r'^section\s+\d+',
    r'^part\s+\d+',
    r'^module\s+guide',
    r'^assessment\s+brief',
    r'^confidentiality',
    r'^academic\s+integrity',
    r'^learning\s+outcomes',
    r'^recommended\s+reading',
    r'^reference\s+list',
    r'^bibliography',
    r'^assessment\s+criteria',
    r'^marking\s+criteria',
    r'^student\s+guidance',
    r'^health\s+and\s+safety'
]
SECTION_PATTERNS = [re.compile(pat, re.IGNORECASE) for pat in SECTION_KEYWORDS]

def is_section_boundary(
    text: str,
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False,
    is_table_header: bool = False
) -> bool:
    """
    Determines if the text represents a SECTION_BOUNDARY.
    """
    if not text:
        return False
        
    cleaned = text.strip()
    if not cleaned:
        return False
        
    # Check if matches any protected section
    if is_protected_section(cleaned):
        return True
        
    # Check explicit section patterns
    for pat in SECTION_PATTERNS:
        if pat.search(cleaned):
            return True
            
    # Check if it meets the heading score threshold
    if is_academic_heading(cleaned, is_bold=is_bold, font_size=font_size, is_standalone=is_standalone):
        return True
        
    # Table section header signals
    if is_table_header:
        # A table section header is bold, short, contains no digits, and is Title Case / UPPERCASE / short phrase
        if is_bold and len(cleaned) < 50 and not re.search(r'\d', cleaned):
            if cleaned.istitle() or cleaned.isupper() or len(cleaned.split()) <= 4:
                return True
                
    return False
