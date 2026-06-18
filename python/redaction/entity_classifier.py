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

LEARNED_CLASSIFICATIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'logs', 'learned_classifications.json'
)

LEARNED_CLASSIFICATIONS = {}

def reload_learned_classifications():
    global LEARNED_CLASSIFICATIONS
    try:
        if os.path.exists(LEARNED_CLASSIFICATIONS_FILE):
            with open(LEARNED_CLASSIFICATIONS_FILE, 'r') as f:
                LEARNED_CLASSIFICATIONS = json.load(f)
        else:
            LEARNED_CLASSIFICATIONS = {}
    except Exception:
        LEARNED_CLASSIFICATIONS = {}

reload_learned_classifications()


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

def _classify_entity_internal(
    text: str,
    context: str = "",
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False
) -> tuple:
    reasons = []
    if not text or not text.strip():
        return "UNKNOWN", "KEEP", ["empty_text"], 0

    # Stage 2 GPT Cached Override check
    from redaction.escalation_manager import get_gpt_classification
    gpt_res = get_gpt_classification(text, context)
    if gpt_res and gpt_res.get("classification"):
        classification = gpt_res["classification"]
        score = gpt_res.get("confidence", 100)
        action = "REDACT" if classification in ("PERSON", "UNIVERSITY_BRANDING", "SUBMISSION_EVENT") else "KEEP"
        reasons = [f"gpt_verified: {classification}"]
        return classification, action, reasons, score

    norm_text = normalize_text(text)

    # 1. PERSON Prefix Rules
    person_prefixes = [
        r"\btutor\s+name\b",
        r"\bmodule\s+leader\b",
        r"\bmodule\s+lead\b",
        r"\bassessor\b",
        r"\binternal\s+verifier\b",
        r"\bmarker\b",
        r"\breviewer\b"
    ]
    combined_ctx = (context or "") + " " + text
    if any(re.search(pref, combined_ctx, re.IGNORECASE) for pref in person_prefixes):
        if len(text.strip()) > 1:
            return "PERSON", "REDACT", ["person_prefix_rule"], 100

    # 2. SUBMISSION EVENT RULES
    submission_events = {
        "draft submission",
        "draft submission (mandatory)",
        "feedback date",
        "submission date",
        "date and time of submission",
        "target feedback date",
        "submission due date",
        "submission date & time"
    }
    if norm_text in submission_events:
        return "SUBMISSION_EVENT", "REDACT", ["submission_event_rule"], 100

    # 3. PROTECTED SECTION RULES
    protected_sections = {
        "recommended reading",
        "reference list",
        "learning outcomes",
        "academic integrity",
        "confidentiality"
    }
    if norm_text in protected_sections:
        return "PROTECTED_SECTION", "KEEP", ["protected_section_rule"], 100

    # 4. UNIVERSITY BRANDING RULES (University Entity Check)
    for uni in UNIVERSITY_NAMES:
        norm_uni = normalize_text(uni)
        if norm_text == norm_uni or is_fuzzy_match(norm_text, norm_uni, threshold=80.0, partial=True):
            reasons.append(f"university_entity_matched: {uni}")
            return "UNIVERSITY_ENTITY", "REDACT", reasons, 90

    # 5. ACADEMIC CONTENT RULES (Academic Exclusion check, Heading check, Academic Title check)
    # 5.1 Academic Exclusion Check
    for excl in ACADEMIC_EXCLUSIONS:
        norm_excl = normalize_text(excl)
        if norm_text == norm_excl or is_fuzzy_match(norm_text, norm_excl, threshold=85.0, partial=True):
            reasons.append(f"academic_exclusion_matched: {excl}")
            return "ACADEMIC_TITLE", "KEEP", reasons, -50

    # 5.2 Heading Detector Check
    heading_detected = is_academic_heading(text, is_bold, font_size, is_standalone)
    is_numbered = is_numbered_section(text)
    if heading_detected or is_numbered:
        if heading_detected:
            reasons.append("heading_detected")
        if is_numbered:
            reasons.append("numbered_section_detected")
        return "SECTION_HEADING", "KEEP", reasons, -30

    # 5.3 Academic Title Detector Check
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

    # 6. BUSINESS FIELD RULES (Business Field Detector Check)
    for rem in BUSINESS_REMOVALS:
        norm_rem = normalize_text(rem)
        if norm_text == norm_rem or is_fuzzy_match(norm_text, norm_rem, threshold=85.0, partial=True):
            reasons.append(f"business_removal_field_matched: {rem}")
            return "BUSINESS_FIELD", "REMOVE_BLOCK", reasons, 100

    # 7. LEARNED CLASSIFICATION CACHE
    if norm_text in LEARNED_CLASSIFICATIONS:
        classification = LEARNED_CLASSIFICATIONS[norm_text]
        action = "REDACT" if classification in ("PERSON", "UNIVERSITY_BRANDING", "SUBMISSION_EVENT") else "KEEP"
        return classification, action, ["learned_consistency_rule"], 100

    # 8. PERSON RULES - HUMAN NAME CLASSIFIER & VALIDATOR (Human Name checks)
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

def classify_entity(
    text: str,
    context: str = "",
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False
) -> tuple:
    # 0. Preservation Engine Check
    from redaction.preservation_engine import PreservationEngine
    pres_res = PreservationEngine.check_preservation(
        text=text,
        context=context,
        is_bold=is_bold,
        font_size=font_size,
        is_standalone=is_standalone
    )
    if pres_res is not None:
        score = 100 if pres_res["reason"] == "PROTECTED_SECTION" else 0
        return pres_res["reason"], "KEEP", ["preservation_engine_override"], score

    # Call original classification
    classification, action, reasons, score = _classify_entity_internal(
        text=text,
        context=context,
        is_bold=is_bold,
        font_size=font_size,
        is_standalone=is_standalone
    )
    
    reasons = list(reasons)

    # Validate decision if it attempts to redact or remove a block
    if action in ("REDACT", "REMOVE_BLOCK"):
        from redaction.sensitivity_score import get_sensitivity_score
        from redaction.redaction_validator import validate_redaction
        
        # 1. Sensitivity score check
        if get_sensitivity_score(classification) < 70:
            action = "KEEP"
            reasons.append("sensitivity_score_too_low")
        # 2. Redaction validation check
        elif not validate_redaction(text, classification):
            action = "KEEP"
            classification = "ACADEMIC_CONTENT"
            reasons.append("redaction_validation_failed")

    return classification, action, reasons, score
