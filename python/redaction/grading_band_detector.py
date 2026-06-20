import re

GRADING_BAND_PATTERNS = [
    r'\bclass\s*i+\b',
    r'\bclass\s*iv\b',
    r'\bexcellent\s+quality\b',
    r'\bvery\s+good\s+quality\b',
    r'\bgood\s+quality\b',
    r'\bsatisfactory\s+quality\b',
    r'\bborderline\s+fail\b',
    r'\bfail\b'
]

GRADING_BAND_REGEX = re.compile('|'.join(GRADING_BAND_PATTERNS), re.IGNORECASE)

def is_grading_band(text: str) -> bool:
    """
    Checks if a candidate's text matches grading band boundaries.
    """
    if not text:
        return False
    return bool(GRADING_BAND_REGEX.search(text.strip()))
