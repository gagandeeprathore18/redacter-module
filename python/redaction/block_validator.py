import os
import json
from redaction.protected_section_detector import get_protected_section_match
from redaction.heading_boundary_detector import is_section_boundary
from redaction.normalizer import normalize_text
from redaction.fuzzy_matcher import is_fuzzy_match

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'config'
)
REMOVABLE_ANCHORS_FILE = os.path.join(CONFIG_DIR, 'removable_anchors.json')

def load_removable_anchors():
    try:
        if os.path.exists(REMOVABLE_ANCHORS_FILE):
            with open(REMOVABLE_ANCHORS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading removable anchors: {e}")
    return []

REMOVABLE_ANCHORS = load_removable_anchors()

def is_valid_anchor(anchor_text: str) -> bool:
    """
    Checks if the anchor text matches any valid removable anchors from configuration.
    """
    if not anchor_text:
        return False
    
    norm_anchor = normalize_text(anchor_text)
    for valid_anchor in REMOVABLE_ANCHORS:
        norm_valid = normalize_text(valid_anchor)
        if norm_valid in norm_anchor or is_fuzzy_match(norm_anchor, norm_valid, threshold=85.0, partial=True):
            return True
    return False

def validate_block_removal(
    anchor_text: str,
    collected_texts: list
) -> tuple[str, str, list]:
    """
    Validates whether a block can be safely removed.
    Returns: (decision, reason, protected_sections_encountered)
    """
    # 1. Anchor check
    if not is_valid_anchor(anchor_text):
        return "DENY", "invalid_anchor", []
        
    # 2. Protected section & boundary checks
    protected_encountered = []
    boundary_crossed = False
    
    for text in collected_texts:
        if not text:
            continue
        protected_match = get_protected_section_match(text)
        if protected_match:
            protected_encountered.append(protected_match)
            
        # Check if boundary is crossed (if text behaves as a boundary and is not the anchor cell itself)
        if text.strip() != anchor_text.strip() and is_section_boundary(text):
            boundary_crossed = True
            
    if protected_encountered:
        return "DENY", "protected_section_detected", protected_encountered
        
    if boundary_crossed:
        return "DENY", "boundary_crossed", []
        
    return "ALLOW", "valid_block", []
