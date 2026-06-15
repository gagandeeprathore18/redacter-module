import os
import json
from redaction.normalizer import normalize_text
from redaction.fuzzy_matcher import is_fuzzy_match

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'config'
)
PROTECTED_SECTIONS_FILE = os.path.join(CONFIG_DIR, 'protected_sections.json')

def load_protected_sections():
    try:
        if os.path.exists(PROTECTED_SECTIONS_FILE):
            with open(PROTECTED_SECTIONS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading protected sections: {e}")
    return []

PROTECTED_SECTIONS = load_protected_sections()

class Section:
    def __init__(self, name: str):
        self.name = name
        self.locked = False

def get_protected_section_match(text: str) -> str:
    """
    Checks if text matches any protected section.
    Returns the matched protected section name if found, else None.
    """
    if not text:
        return None
    norm_text = normalize_text(text)
    for section in PROTECTED_SECTIONS:
        norm_sec = normalize_text(section)
        # Exact match or fuzzy match
        if norm_sec == norm_text or is_fuzzy_match(norm_text, norm_sec, threshold=85.0, partial=True):
            return section
    return None

def check_protected_section(text: str) -> Section:
    matched = get_protected_section_match(text)
    if matched:
        sec = Section(matched)
        sec.locked = True
        return sec
    return None

def is_protected_section(text: str) -> bool:
    return get_protected_section_match(text) is not None
