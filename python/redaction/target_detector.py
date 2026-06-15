import re
import json
import os
from redaction.normalizer import normalize_text
from redaction.fuzzy_matcher import is_fuzzy_match
from redaction.confidence_engine import should_redact
from redaction.audit_logger import log_candidate

# Configuration files
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
ACADEMIC_EXCLUSIONS_FILE = os.path.join(CONFIG_DIR, 'academic_exclusions.json')
BUSINESS_REMOVALS_FILE = os.path.join(CONFIG_DIR, 'business_removals.json')
UNIVERSITY_NAMES_FILE = os.path.join(CONFIG_DIR, 'university_names.json')

def load_json_config(file_path: str, default_val: list) -> list:
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading config {file_path}: {e}")
    return default_val

ACADEMIC_EXCLUSIONS = load_json_config(ACADEMIC_EXCLUSIONS_FILE, [])
BUSINESS_REMOVALS = load_json_config(BUSINESS_REMOVALS_FILE, [])
UNIVERSITY_NAMES = load_json_config(UNIVERSITY_NAMES_FILE, [])

DEFAULT_TARGETS = [
    r'\bsubmission\s+(?:location|point|portal|platform|link|method|box|folder|area|mode|type|system|channel|url|address|site|page|form)\b',
    r'\bsubmit(?:ted)?\s+(?:to|via|through|using|on|at|by|with)\b',
    r'\bhow\s+to\s+submit\b',
    r'\bwhere\s+to\s+submit\b',
    r'\belectronic(?:ally)?\s+submit(?:ted)?\b',
    r'\bonline\s+submission\b',
    r'\be-?submission\b',
    r'\bupload\s+(?:location|link|portal|to)\b',
    r'\bsubmission\s+details\b',
    r'\bsubmission\s+deadline\b',
    r'\bdeadline(?:s)?\b',
    r'\bsubmission\s+due\s+(?:dates?/time|date|time)\b',
    r'\bfeedback\s+date\b',
    r'\breturn\s+date\b',
    r'\bprovisional\s+marks\b',
    r'\bwritten\s+feedback\b',
]

def detect_targets(grid: dict, keywords=None) -> list:
    """
    Returns a list of (r, c) tuples where a target label is matched.
    """
    from redaction.entity_classifier import classify_entity
    target_coordinates = []
    for coord, cell in grid.items():
        text = cell.text
        if not text:
            continue
            
        classification, action, reasons, score = classify_entity(text)
        
        # Log to audit logger
        log_candidate(candidate=text, classification=classification, action=action, score=score, reasons=reasons)
        
        if action in ("remove", "REMOVE", "REMOVE_BLOCK", "remove_block"):
            target_coordinates.append(coord)
            
    return target_coordinates
