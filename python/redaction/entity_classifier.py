import os
import json
import re
from redaction.normalizer import normalize_text
from redaction.fuzzy_matcher import is_fuzzy_match
from redaction.heading_detector import is_academic_heading, is_numbered_section
from redaction.academic_title_detector import detect_academic_title
from redaction.human_name_validator import validate_human_name
from redaction.human_name_classifier import score_human_name
from redaction.confidence_engine import evaluate_human_name
from redaction.audit_logger import log_candidate

# Load config files
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
ACADEMIC_EXCLUSIONS_FILE = os.path.join(CONFIG_DIR, 'academic_exclusions.json')
BUSINESS_REMOVALS_FILE = os.path.join(CONFIG_DIR, 'business_removals.json')
UNIVERSITY_NAMES_FILE = os.path.join(CONFIG_DIR, 'university_names.json')

def load_json_config(file_path: str) -> list:
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

ACADEMIC_EXCLUSIONS = load_json_config(ACADEMIC_EXCLUSIONS_FILE)
BUSINESS_REMOVALS = load_json_config(BUSINESS_REMOVALS_FILE)
UNIVERSITY_NAMES = load_json_config(UNIVERSITY_NAMES_FILE)

def classify_entity(
    text: str,
    context: str = "",
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False
) -> tuple:
    """
    Classifies the text candidate using the 8-step pipeline:
    1. Academic Exclusion Check
    2. Heading Detector Check
    3. Academic Title Detector Check
    4. Business Field Detector Check
    5. University Entity Detector Check
    6. Human Name Classifier & Validator
    7. Confidence Engine
    8. Action Engine
    
    Returns: (classification, action, reasons, score)
    """
    reasons = []
    if not text or not text.strip():
        return "UNKNOWN", "KEEP", ["empty_text"], 0

    norm_text = normalize_text(text)

    # Step 1: Academic Exclusion Check
    for excl in ACADEMIC_EXCLUSIONS:
        norm_excl = normalize_text(excl)
        if norm_text == norm_excl or is_fuzzy_match(norm_text, norm_excl, threshold=85.0, partial=True):
            reasons.append(f"academic_exclusion_matched: {excl}")
            return "ACADEMIC_TITLE", "KEEP", reasons, -50

    # Step 2: Heading Detector Check
    heading_detected = is_academic_heading(text, is_bold, font_size, is_standalone)
    is_numbered = is_numbered_section(text)
    if heading_detected or is_numbered:
        if heading_detected:
            reasons.append("heading_detected")
        if is_numbered:
            reasons.append("numbered_section_detected")
        return "SECTION_HEADING", "KEEP", reasons, -30

    # Step 3: Academic Title Detector Check
    is_academic_title, matched_term = detect_academic_title(text)
    is_business_field = False
    for rem in BUSINESS_REMOVALS:
        norm_rem = normalize_text(rem)
        if norm_text == norm_rem or is_fuzzy_match(norm_text, norm_rem, threshold=85.0, partial=True):
            is_business_field = True
            break
            
    if is_academic_title and not is_business_field:
        reasons.append(f"academic_term_detected: {matched_term}")
        return "ACADEMIC_TITLE", "KEEP", reasons, -40

    # Step 4: Business Field Detector Check
    for rem in BUSINESS_REMOVALS:
        norm_rem = normalize_text(rem)
        if norm_text == norm_rem or is_fuzzy_match(norm_text, norm_rem, threshold=85.0, partial=True):
            reasons.append(f"business_removal_field_matched: {rem}")
            return "BUSINESS_FIELD", "REMOVE_BLOCK", reasons, 100

    # Step 5: University Entity Detector Check
    for uni in UNIVERSITY_NAMES:
        norm_uni = normalize_text(uni)
        if norm_text == norm_uni or is_fuzzy_match(norm_text, norm_uni, threshold=80.0, partial=True):
            reasons.append(f"university_entity_matched: {uni}")
            return "UNIVERSITY_ENTITY", "REDACT", reasons, 90

    # Step 6: Human Name Classifier & Validator
    is_valid_name, val_reason = validate_human_name(text)
    if not is_valid_name:
        reasons.append(val_reason)
        return "UNKNOWN", "KEEP", reasons, 0

    base_name_score = score_human_name(text, context)
    
    # Step 7: Confidence Engine
    final_score, should_redact_name = evaluate_human_name(
        base_name_score=base_name_score,
        heading_detected=heading_detected,
        has_academic_keyword=is_academic_title,
        is_numbered=is_numbered
    )

    if should_redact_name:
        words = text.split()
        if len(words) == 2:
            reasons.append("two_word_name")
        elif len(words) >= 3:
            reasons.append("multi_word_name")
        if context:
            reasons.append("context_proximity_match")
        return "PERSON", "REDACT", reasons, final_score

    reasons.append("confidence_score_too_low")
    return "UNKNOWN", "KEEP", reasons, final_score
