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
        # GPT is authoritative: derive action from GPT payload or fall back to canonical map
        action = gpt_res.get("action")
        if action == "PRESERVE":
            action = "KEEP"
        elif action != "REDACT":
            if classification in ("UNIVERSITY_BRANDING", "UNIVERSITY_ENTITY"):
                action = "REDACT"
            else:
                _REDACT_CLASSES = {
                    "PERSON", "METADATA_FIELD", "BUSINESS_FIELD", "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE"
                }
                action = "REDACT" if classification in _REDACT_CLASSES else "KEEP"
        reasons = [f"gpt_verified: {classification}"]
        return classification, action, reasons, score

    norm_text = normalize_text(text)

    # Academic Scheduling Terms Pregate: Never redact these academic terms
    ACADEMIC_SCHEDULING_TERMS = {
        "submit", "submitted", "submission", "feedback", "assessment", "deadline", "release",
        "formative feedback", "summative feedback", "assessment and feedback",
        "presentation requirements", "submission requirements"
    }
    if any(term in norm_text for term in ACADEMIC_SCHEDULING_TERMS):
        return "ACADEMIC_CONTENT", "KEEP", ["academic_scheduling_terms_pregate"], 100

    # 1. PERSON Prefix Rules
    # Priority 2: validate with human name validator before assigning PERSON
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
            is_valid_person, _reason = validate_human_name(text)
            if is_valid_person:
                return "PERSON", "REDACT", ["person_prefix_rule"], 100
            else:
                reasons.append(f"person_prefix_rejected: {_reason}")

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
        match_found = False
        if len(norm_text) <= 4 or len(norm_uni) <= 4:
            match_found = (norm_text == norm_uni)
        else:
            match_found = (norm_text == norm_uni or is_fuzzy_match(norm_text, norm_uni, threshold=80.0, partial=True))
        if match_found:
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
        if classification in ("UNIVERSITY_BRANDING", "UNIVERSITY_ENTITY"):
            action = "REDACT"
        else:
            action = "REDACT" if classification in ("PERSON", "SUBMISSION_EVENT", "METADATA_FIELD", "BUSINESS_FIELD") else "KEEP"
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

# ---------------------------------------------------------------------------
# Detector → Classification lock map  (Priority 1)
# When a detector fires with a definitive source, lock the classification
# so downstream steps cannot overwrite it to UNKNOWN.
# ---------------------------------------------------------------------------
_DETECTOR_CLASSIFICATION_LOCK = {
    "METADATA_FIELD_PATTERN":    ("METADATA_FIELD",    "REMOVE_BLOCK"),
    "PROTECTED_SECTION_PATTERN": ("PROTECTED_SECTION", "KEEP"),
    "ACADEMIC_CONTENT_PATTERN":  ("ACADEMIC_CONTENT",  "KEEP"),
    "ACADEMIC_TITLE_PATTERN":    ("ACADEMIC_TITLE",    "KEEP"),
    "DATE_CANDIDATE_PATTERN":    ("DATE_CANDIDATE",    "REDACT"),
    "TIME_VAL_PATTERN":          ("TIME_VALUE",        "REDACT"),
}

# Final decision matrix  (Priority 8)
_FINAL_DECISION_MATRIX = {
    "PERSON":              "REDACT",
    "UNIVERSITY_BRANDING": "REDACT",
    "UNIVERSITY_ENTITY":   "REDACT",
    "METADATA_FIELD":      "REMOVE_BLOCK",
    "BUSINESS_FIELD":      "REMOVE_BLOCK",
    "DATE_CANDIDATE":      "REDACT",
    "TIME_VALUE":          "REDACT",
    "ADMINISTRATIVE_DATE": "REDACT",
    "ACADEMIC_DATE":        "KEEP",
    "ACADEMIC_CONTENT":    "KEEP",
    "ACADEMIC_TITLE":      "KEEP",
    "PROTECTED_SECTION":   "KEEP",
    "SECTION_HEADING":     "KEEP",
    "PARAGRAPH_CONTENT":   "KEEP",
    "UNKNOWN":             "KEEP",
}


def classify_entity(
    text: str,
    context: str = "",
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False,
    source_detector: str = "",
    in_table: bool = False,
    parent_word_count: int = 0
) -> tuple:
    # Pre-gates and Allowlists (Drafter Module Accuracy Improvement Plan)
    if text:
        norm_text = text.lower().strip()
        if "qualifi" in norm_text or "qualify" in norm_text:
            return "UNIVERSITY_BRANDING", "REDACT", ["qualifi_branding_pregate"], 100

        # ---------------------------------------------------------------
        # Historical Date Filter (Year < 2015)
        # ---------------------------------------------------------------
        if source_detector == "DATE_CANDIDATE_PATTERN":
            four_digit_years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
            if four_digit_years:
                years = [int(y) for y in four_digit_years]
                if any(y < 2015 for y in years):
                    try:
                        from redaction.redaction_audit import RedactionAudit
                        RedactionAudit.log({
                            "candidate": text,
                            "stage": "HISTORICAL_DATE_FILTER",
                            "classification": "ACADEMIC_DATE",
                            "decision": "KEEP",
                            "reason": f"historical_date_auto_preserved: {years}"
                        })
                    except Exception:
                        pass
                    return "ACADEMIC_DATE", "KEEP", ["historical_date_filter"], 100

        if source_detector and source_detector in _DETECTOR_CLASSIFICATION_LOCK:
            locked_cls, locked_action = _DETECTOR_CLASSIFICATION_LOCK[source_detector]
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "CLASSIFICATION_LOCK",
                "classification": locked_cls,
                "decision": "KEEP" if locked_action == "KEEP" else "REMOVE",
                "reason": f"detector_lock: {source_detector}",
                "confidence": 100,
            })
            return locked_cls, locked_action, [f"detector_lock: {source_detector}"], 100

        # ---------------------------------------------------------------
        # Priority 6 – Table Protection
        # Candidates inside tables with ambiguous classification → KEEP
        # ---------------------------------------------------------------
        _TABLE_PRESERVE_CLASSES = {"UNKNOWN", "ACADEMIC_CONTENT", "ACADEMIC_TITLE"}

        # Academic Concepts Preservation Pregate (MUST NEVER become BUSINESS_FIELD)
        # ------------------------------------------------------------------
        # Academic Concepts Preservation Pregate
        # These terms must NEVER become BUSINESS_FIELD or metadata.
        # Use phrase containment rather than exact-match.
        # ------------------------------------------------------------------

        MUST_NEVER_BE_BUSINESS_FIELD = {
            "research",
            "research proposal",
            "research project",
            "research methods",
            "research skills",
            "research topic",
            "research topic and context",
            "research aim",
            "research objectives",
            "research aim and objectives",
            "research methodology",
            "research methodology and data collection",
            "research ethics",

            "methodology",
            "literature review",
            "findings",
            "analysis",
            "discussion",
            "recommendations",
            "findings and analysis",
            "recommendations and conclusion",

            "presentation",
            "presentation requirements",
            "presentation structure",
            "presentation guidelines",

            "dissertation",
            "coursework",

            "assessment criteria",
            "learning outcomes",
            "recommended reading",

            "study hours",
            "guided study hours",
            "scheduled teaching hours",

            "ethical approval requirement"
        }

        PROTECTED_SECTION_TERMS = {
            "learning outcomes",
            "recommended reading",
            "reference list",
            "academic integrity",
            "confidentiality"
        }

        if any(
            term in norm_text
            for term in MUST_NEVER_BE_BUSINESS_FIELD
        ):
            if any(
                term in norm_text
                for term in PROTECTED_SECTION_TERMS
            ):
                return (
                    "PROTECTED_SECTION",
                    "KEEP",
                    ["protected_section_pregate"],
                    100
                )

            try:
                from redaction.redaction_audit import RedactionAudit
                RedactionAudit.log({
                    "candidate": text,
                    "stage": "ACADEMIC_PRE_GATE",
                    "classification": "ACADEMIC_CONTENT",
                    "decision": "KEEP",
                    "matched_terms": [
                        term for term in MUST_NEVER_BE_BUSINESS_FIELD
                        if term in norm_text
                    ]
                })
            except Exception:
                pass

            return (
                "ACADEMIC_CONTENT",
                "KEEP",
                ["academic_concept_pregate"],
                100
            )

        # Metadata Field Detector Pregate
        from redaction.metadata_field_detector import is_metadata_field, is_metadata_field_to_keep
        if is_metadata_field(text):
            if is_metadata_field_to_keep(text):
                return "METADATA_FIELD", "KEEP", ["metadata_field_keep_gate"], 100
            return "METADATA_FIELD", "REMOVE_BLOCK", ["metadata_field_detector_pregate"], 100

        # Allowlists
        ACADEMIC_ALLOWLIST = {"application", "category a", "category b", "category c"}
        ASSESSMENT_TYPES = {"dissertation", "presentation", "group presentation", "coursework", "portfolio", "research report", "reflective report", "case study"}
        LMS_PLATFORMS = {"canvas", "blackboard", "turnitin", "moodle"}

        if norm_text in ACADEMIC_ALLOWLIST:
            return "ACADEMIC_CONTENT", "KEEP", ["academic_allowlist_pregate"], 0

        if norm_text in ASSESSMENT_TYPES:
            return "ACADEMIC_CONTENT", "KEEP", ["assessment_type_pregate"], 0

        if norm_text in LMS_PLATFORMS:
            return "ACADEMIC_CONTENT", "KEEP", ["lms_platform_pregate"], 0

        # Paragraph Detector Pre-gate
        from redaction.paragraph_detector import is_paragraph
        if is_paragraph(text):
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "PARAGRAPH_FILTER",
                "decision": "PRESERVED",
                "reason": "PARAGRAPH_CONTENT"
            })
            return "PARAGRAPH_CONTENT", "KEEP", ["paragraph_detector_pregate"], 0

        # Grading Band Detector Pre-gate
        from redaction.grading_band_detector import is_grading_band
        if is_grading_band(text):
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "GRADING_BAND_FILTER",
                "decision": "PRESERVED",
                "reason": "GRADING_BAND"
            })
            return "ACADEMIC_CONTENT", "KEEP", ["grading_band_detector_pregate"], 0

        # Rubric Detector Pre-gate
        from redaction.rubric_detector import is_rubric_text
        if is_rubric_text(text, context):
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "RUBRIC_FILTER",
                "decision": "PRESERVED",
                "reason": "RUBRIC_CONTENT"
            })
            return "ACADEMIC_CONTENT", "KEEP", ["rubric_detector_pregate"], 0

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
        from redaction.redaction_audit import RedactionAudit
        RedactionAudit.log({
            "candidate": text,
            "stage": "PRESERVATION_ENGINE",
            "decision": "PRESERVED",
            "reason": pres_res["reason"]
        })
        return pres_res["reason"], "KEEP", ["preservation_engine_override"], score

    # Heading / Structural pre-gate checks (Phase 3 Integration)
    try:
        from redaction.heading_detector import HeadingDetector
        from redaction.structural_content_detector import StructuralContentDetector

        if HeadingDetector.is_heading(text):
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "HEADING_FILTER",
                "decision": "REJECTED",
                "reason": "HEADING_CONTENT"
            })
            return "SECTION_HEADING", "KEEP", ["heading_detector_pregate"], -30

        struct_cat = StructuralContentDetector.get_category(text)
        if struct_cat:
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "STRUCTURAL_FILTER",
                "decision": "REJECTED",
                "reason": struct_cat
            })
            return struct_cat, "KEEP", ["structural_content_detector_pregate"], -30
    except Exception:
        pass

    # Call original classification
    classification, action, reasons, score = _classify_entity_internal(
        text=text,
        context=context,
        is_bold=is_bold,
        font_size=font_size,
        is_standalone=is_standalone
    )

    reasons = list(reasons)
    gpt_source = bool(reasons and reasons[0].startswith("gpt_verified:"))

    # ---------------------------------------------------------------
    # Priority 6 – Table Protection (post-classification)
    # Inside tables, UNKNOWN/ACADEMIC/TITLE → always KEEP
    # ---------------------------------------------------------------
    if in_table and classification in ("UNKNOWN", "ACADEMIC_CONTENT", "ACADEMIC_TITLE", "BUSINESS_FIELD"):
        action = "KEEP"
        reasons.append("table_context_protection")

    # NEVER redact UNKNOWN rule
    if classification == "UNKNOWN":
        norm_text = text.lower().strip()
        protected_keywords = ["confidentiality", "integrity", "learning", "reading", "reference", "criteria", "outcomes"]
        is_high_impact_action = any(kw in norm_text for kw in protected_keywords)
        if score > 95 and is_high_impact_action:
            action = "REDACT"
        else:
            action = "KEEP"

    # Validate decision if it attempts to redact or remove a block
    # NOTE: These checks are BYPASSED for GPT-authoritative decisions.
    # GPT's classification is final and cannot be overridden by Python heuristics.
    if not gpt_source and action in ("REDACT", "REMOVE_BLOCK"):
        if classification in ("PERSON", "UNKNOWN") and len(text.split()) > 5:
            action = "KEEP"
            reasons.append("preservation_first_long_candidate")
        else:
            from redaction.sensitivity_score import get_sensitivity_score
            from redaction.redaction_validator import validate_redaction

            # 1. Sensitivity score check (skip if UNKNOWN is explicitly allowed to be redacted)
            if classification != "UNKNOWN" and get_sensitivity_score(classification) < 70:
                action = "KEEP"
                reasons.append("sensitivity_score_too_low")
            # 2. Redaction validation check
            elif not validate_redaction(text, classification):
                action = "KEEP"
                classification = "ACADEMIC_CONTENT"
                reasons.append("redaction_validation_failed")

    # ---------------------------------------------------------------
    # Priority 4 – Context Protection Layer
    # Parent block and fragment guards applied after all other logic.
    # NOTE: Bypassed for GPT-authoritative decisions.
    # ---------------------------------------------------------------
    try:
        from redaction.context_protection import should_preserve_by_context
        if not gpt_source and action in ("REDACT", "REMOVE_BLOCK"):
            ctx_preserve, ctx_reason = should_preserve_by_context(
                text=text,
                classification=classification,
                parent_word_count=parent_word_count
            )
            if ctx_preserve:
                action = "KEEP"
                reasons.append(f"context_protection: {ctx_reason}")
    except Exception:
        pass

    # ---------------------------------------------------------------
    # Priority 8 – Final Decision Hierarchy
    # Enforce the canonical action for each classification.
    # NOTE: Bypassed entirely for GPT-authoritative decisions.
    # GPT's returned classification already maps to the correct action.
    # ---------------------------------------------------------------
    if not gpt_source:
        canonical_action = _FINAL_DECISION_MATRIX.get(classification)
        if canonical_action is not None:
            if canonical_action == "KEEP" and action in ("REDACT", "REMOVE_BLOCK", "REPLACE"):
                _ALWAYS_REDACT_OR_REPLACE = {"PERSON", "METADATA_FIELD",
                                             "UNIVERSITY_BRANDING", "UNIVERSITY_ENTITY", "BUSINESS_FIELD",
                                             "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE"}
                if classification not in _ALWAYS_REDACT_OR_REPLACE:
                    action = "KEEP"
                    reasons.append("final_decision_matrix_override")

    # Phase 4 Log: Classification Decisions
    from redaction.redaction_audit import RedactionAudit
    classifier_name = reasons[0] if reasons else "UNKNOWN_RULE"
    RedactionAudit.log({
        "candidate": text,
        "stage": "CLASSIFICATION",
        "classification": classification,
        "confidence": score,
        "classifier": classifier_name
    })

    return classification, action, reasons, score

