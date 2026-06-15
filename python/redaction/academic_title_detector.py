import json
import os
from redaction.normalizer import normalize_text
from redaction.fuzzy_matcher import is_fuzzy_match

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
ACADEMIC_TERMS_FILE = os.path.join(CONFIG_DIR, 'academic_terms.json')

def load_academic_terms() -> list:
    try:
        if os.path.exists(ACADEMIC_TERMS_FILE):
            with open(ACADEMIC_TERMS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading academic terms: {e}")
    return []

ACADEMIC_TERMS = load_academic_terms()

def detect_academic_title(text: str) -> tuple:
    """
    Checks if text contains academic terms.
    Returns: (is_academic, matched_term)
    """
    if not text:
        return False, None
        
    norm_text = normalize_text(text)
    # Split text into normalized words to check word by word or substring matching
    words = norm_text.split()
    
    for term in ACADEMIC_TERMS:
        norm_term = normalize_text(term)
        # Check if term is in text (word boundary or substring match)
        if norm_term in words or is_fuzzy_match(norm_text, norm_term, threshold=85.0, partial=True):
            return True, term
            
    return False, None
