"""
stop_patterns.py
----------------
Single source of truth for block-expansion stop patterns.

All three processors (DOCX, PDF, PPTX) and the relationship_detector import
`should_stop_block` from here so that stopping behaviour is identical across
every engine.
"""

import re

# Union of every stop keyword from docx_processor, pdf_processor, pptx_processor
# and relationship_detector. PDF had the most (added assessment outline, overview,
# module code, module title, word count, contribution).
SHARED_STOP_LABELS = [
    r'\blearning\s+outcomes?\b',
    r'\bassessment\s+criteria\b',
    r'\bfeedback\s+date\b',
    r'\bmodule\s+name\b',
    r'\bprogramme\b',
    r'\bmodule\s+leader\b',
    r'\btutor\b',
    r'\blecturer\b',
    r'\bassessment\s+weighting\b',
    r'\bcourse\b',
    r'\bassignment\b',
    r'\bweighting\b',
    r'\bcredits\b',
    r'\blevel\b',
    r'\bsigned\b',
    r'\bsignature\b',
    r'\bassessor\b',
    r'\bexaminer\b',
    r'\bmoderator\b',
    r'\blo\d+\b',
    # PDF-specific additions now shared by everyone
    r'\bassessment\s+outline\b',
    r'\boverview\b',
    r'\bmodule\s+code\b',
    r'\bmodule\s+title\b',
    r'\bword\s+count\b',
    r'\bcontribution\b',
]

SHARED_STOP_PATTERNS = [re.compile(pat, re.IGNORECASE) for pat in SHARED_STOP_LABELS]


def should_stop_block(text: str) -> bool:
    """
    Unified block-expansion stop check used by all three processors and the
    relationship detector.

    Returns True if the text signals that expansion should stop:
    - Protected section (confidentiality, academic integrity, …)
    - Section boundary / heading
    - A label-with-colon that is not an Option continuation
    - Any stop-pattern keyword
    - Horizontal separator lines
    """
    from redaction.boundary_validator import should_stop_expansion

    if not text:
        return False

    cleaned = text.strip()
    if not cleaned:
        return False

    # Delegate to the shared boundary validator first (protected sections + headings)
    if should_stop_expansion(cleaned):
        return True

    # Stop-pattern keywords
    for pat in SHARED_STOP_PATTERNS:
        if pat.search(cleaned):
            return True

    # Generic label-with-colon heuristic:
    # A line like "Module Name: ..." signals a new field → stop.
    # But "Option A: ..." is a valid continuation → don't stop.
    if re.search(r'^[A-Z][A-Za-z0-9\s\-()\&/]{2,100}:', cleaned):
        label_part = cleaned.split(':')[0].strip().lower()
        if 'option' not in label_part:
            return True

    return False
