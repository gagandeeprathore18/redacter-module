"""
Heading Detector
================
Identifies document headings, section titles, and structural labels that
are NOT redactable entities and must be excluded from the candidate pipeline.

Provides:
    HeadingDetector.is_heading(text) -> bool
    HeadingDetector.get_category(text) -> str | None

Detection rules (in priority order):
    1. Exact match against KNOWN_HEADINGS blacklist
    2. Exact match against PROTECTED_HEADINGS (preserve, never redact)
    3. Learned headings from logs/learned_headings.json
    4. Short (2-4 word) title-case phrase with no digits/email/date/punctuation
    5. Numbered section pattern (e.g. "1.2 Methodology")
    6. Document section label list
"""

import re
import os
import json
import threading

# ---------------------------------------------------------------------------
# Static heading dictionaries
# ---------------------------------------------------------------------------

KNOWN_HEADINGS = {
    # Assignment / module structure
    "assignment brief",
    "your assignment",
    "the assignment",
    "module information",
    "course information",
    "module overview",
    "course overview",
    "module handbook",
    "programme information",
    "programme overview",
    # Navigation labels
    "getting support",
    "achievement team",
    "inclusion services",
    "student support",
    "support services",
    "contact information",
    "contact details",
    "further support",
    "additional support",
    "useful links",
    "key contacts",
    # Document sections
    "executive summary",
    "introduction",
    "conclusion",
    "conclusions",
    "background",
    "overview",
    "summary",
    "methodology",
    "methods",
    "findings",
    "results",
    "discussion",
    "recommendations",
    "appendix",
    "appendices",
    "glossary",
    "abstract",
    "preface",
    "foreword",
    "acknowledgements",
    "acknowledgments",
    "table of contents",
    "list of figures",
    "list of tables",
    # Reference sections
    "references",
    "reference list",
    "list of references",
    "bibliography",
    "recommended reading",
    "further reading",
    "reading list",
    # Academic structure
    "learning outcomes",
    "intended learning outcomes",
    "module aims",
    "assessment criteria",
    "grading criteria",
    "marking criteria",
    "grade descriptors",
    "submission guidance",
    "academic integrity",
    "academic misconduct",
    "plagiarism policy",
    "research ethics",
    "ethical considerations",
    "research methodology",
    "data analysis",
    "literature review",
    "theoretical framework",
    "conceptual framework",
    # Misc structural labels
    "table of contents",
    "contents",
    "key information",
    "important information",
    "general information",
    "additional information",
}

# These headings are explicitly protected — they must NEVER be redacted
PROTECTED_HEADINGS = {
    "learning outcomes",
    "academic integrity",
    "recommended reading",
    "reference list",
    "research ethics",
    "harvard referencing",
    "grading criteria",
    "assessment criteria",
    "marking criteria",
    "submission guidance",
    "research methodology",
    "ethical considerations",
}

# Academic section terms that must NEVER be treated as headings.
# They must pass through to the classification engine so they can be
# correctly labelled ACADEMIC_CONTENT / ACADEMIC_TITLE and preserved.
ACADEMIC_HEADINGS = {
    "research methods",
    "research proposal",
    "research ethics",
    "research questions",
    "research design",
    "research and analysis",
    "learning outcomes",
    "assessment criteria",
    "recommended reading",
    "literature review",
    "methodology",
    "findings",
    "analysis",
    "discussion",
    "conclusion",
    "references",
    "engaging with practice",
    "realisation and communication",
    "independent study hours",
    "guided study hours",
    "scheduled teaching hours",
    "study hours",
    "generic grading criteria",
    "grading criteria",
    "assessment guidance",
    "ethical considerations",
    "research methodology",
    "data collection",
    "data analysis",
    "theoretical framework",
    "conceptual framework",
    # Submission events — must reach _classify_entity_internal's submission_events check
    "draft submission",
    "draft submission (mandatory)",
    "feedback date",
    "submission date",
    "date and time of submission",
    "target feedback date",
    "submission due date",
    "submission date & time",
    "submission deadline",
    "feedback release date",
}


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_NUMBERED_SECTION = re.compile(r'^\d+(?:\.\d+)*\.?\s+[A-Z]')
_HAS_DIGIT        = re.compile(r'\d')
_HAS_EMAIL        = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_HAS_DATE         = re.compile(
    r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
    re.IGNORECASE
)
_HAS_PUNCT        = re.compile(r'[,;:!?@#$%^&*()_+=\[\]{}|<>/\\]')
_ALL_CAPS_WORD    = re.compile(r'\b[A-Z]{2,}\b')  # ALL-CAPS words (e.g. acronyms)

# ---------------------------------------------------------------------------
# Learned headings cache  (logs/learned_headings.json)
# ---------------------------------------------------------------------------

_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs"
)
LEARNED_HEADINGS_FILE = os.path.join(_LOGS_DIR, "learned_headings.json")
_learned_lock = threading.Lock()
_learned_headings: dict = {}


def _load_learned_headings() -> dict:
    """Load learned headings from disk."""
    try:
        if os.path.exists(LEARNED_HEADINGS_FILE):
            with open(LEARNED_HEADINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_learned_headings(data: dict) -> None:
    os.makedirs(_LOGS_DIR, exist_ok=True)
    try:
        with open(LEARNED_HEADINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[heading_detector] Failed to save learned headings: {e}")


def reload_learned_headings() -> None:
    global _learned_headings
    with _learned_lock:
        _learned_headings = _load_learned_headings()


def promote_to_learned(text: str) -> None:
    """Promote a heading candidate to the learned headings file."""
    key = text.strip().lower()
    with _learned_lock:
        _learned_headings[key] = True
        _save_learned_headings(_learned_headings)


# Load on module import
reload_learned_headings()


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

STRUCTURAL_KEYWORDS = {
    "support", "services", "team", "brief", "assignment", "getting", "achievement", "executive", "summary",
    "information", "outcomes", "criteria", "guidance", "integrity", "misconduct", "policy", "ethics",
    "considerations", "methodology", "data", "analysis", "literature", "review", "framework", "reading",
    "list", "references", "bibliography", "contents", "figures", "tables", "overview", "handbook", "aims",
    "introduction", "conclusion", "conclusions", "background", "methods", "findings", "results",
    "discussion", "recommendations", "appendix", "appendices", "glossary", "abstract", "preface",
    "foreword", "acknowledgements", "acknowledgments", "grade", "descriptors", "marking", "grading",
    "assessment", "submission", "feedback", "course", "module", "programme", "unit", "contact",
    "details", "links", "contacts", "guideline", "guidelines", "rubric", "rubrics", "project", "task",
    "tasks", "activity", "activities", "requirement", "requirements", "instruction", "instructions",
    "aim", "objective", "objectives", "guide", "briefing", "schedule", "timetable", "deadlines", "deadline",
    "date", "dates", "time", "times", "descriptor", "descriptors", "grades",
    "mark", "marks", "weighting", "weightings", "percentage", "percent", "credits", "credit", "level",
    "head", "director", "manager", "officer", "coordinator", "administrator"
}

def _is_title_case_heading(text: str) -> bool:
    """
    Detect short (2-4 word) title-case phrases that are structural labels.
    Rules:
    - 2 to 4 words
    - Every word starts with uppercase
    - No digits
    - No email address
    - No date
    - No disqualifying punctuation (commas, colons, etc.)
    - No ALL-CAPS words (those are acronyms, not headings in this context)
    - Must contain at least one known structural keyword to avoid false-positive names
    """
    words = text.strip().split()
    if not (2 <= len(words) <= 4):
        return False
    # All words must start uppercase
    if not all(w and w[0].isupper() for w in words):
        return False
    if _HAS_DIGIT.search(text):
        return False
    if _HAS_EMAIL.search(text):
        return False
    if _HAS_DATE.search(text):
        return False
    if _HAS_PUNCT.search(text):
        return False
    # Reject if any word is fully uppercase with 2+ chars (acronym, not a heading word)
    if any(_ALL_CAPS_WORD.fullmatch(w) for w in words if len(w) > 2):
        return False
    # Check if at least one word is a structural keyword
    if not any(w.lower() in STRUCTURAL_KEYWORDS for w in words):
        return False
    return True



def _is_section_label(text: str) -> bool:
    """
    Returns True if the text looks like a classic document section heading
    (single word or known academic section title).
    """
    norm = text.strip().lower()
    single_word_sections = {
        "introduction", "background", "overview", "summary", "conclusion",
        "conclusions", "methodology", "methods", "findings", "results",
        "discussion", "recommendations", "appendix", "appendices", "glossary",
        "abstract", "preface", "foreword", "acknowledgements", "acknowledgments",
        "references", "bibliography", "contents",
    }
    return norm in single_word_sections


def _is_numbered_section(text: str) -> bool:
    """Detect numbered section titles: '1.2 Methodology', '3. Findings'."""
    cleaned = text.strip()
    if _HAS_DATE.search(cleaned):
        return False
    return bool(_NUMBERED_SECTION.match(cleaned))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class HeadingDetector:
    """
    Stateless detector for document headings and structural labels.
    All methods are class-level (no instantiation needed).
    """

    @classmethod
    def is_heading(cls, text: str) -> bool:
        """
        Returns True if the text is a document heading / structural label
        and should be SKIPPED from the candidate pipeline entirely.

        IMPORTANT: Terms in ACADEMIC_HEADINGS are never treated as headings.
        They must pass through to the classification engine for preservation.
        """
        if not text or not text.strip():
            return False

        norm = text.strip().lower()

        # Priority 0 – Academic headings must NEVER be filtered here.
        # They pass through to the classification / preservation engine.
        if norm in ACADEMIC_HEADINGS:
            return False

        # Metadata fields are not headings
        try:
            from redaction.metadata_field_detector import is_metadata_field
            if is_metadata_field(text):
                return False
        except Exception:
            pass

        # Rule 1 – Exact known heading match
        if norm in KNOWN_HEADINGS:
            return True

        # Rule 1b – Protected heading: also a heading (pass-through to preserve logic)
        # We return False so they reach the preservation engine correctly.
        if norm in PROTECTED_HEADINGS:
            return False

        # Rule 2 – Learned headings from file
        with _learned_lock:
            if norm in _learned_headings:
                return True

        # Rule 3 – Single-word academic section label
        if _is_section_label(text):
            return True

        # Rule 4 – Short title-case pattern
        if _is_title_case_heading(text):
            return True

        # Rule 5 – Numbered section
        if _is_numbered_section(text):
            return True

        return False


    @classmethod
    def is_protected_heading(cls, text: str) -> bool:
        """
        Returns True if this is a heading that should be explicitly PRESERVED
        (never redacted, even if it somehow enters the pipeline).
        """
        return text.strip().lower() in PROTECTED_HEADINGS

    @classmethod
    def get_category(cls, text: str) -> str | None:
        """
        Returns the structural category of a heading, or None if not a heading.
        Used for Phase 5 telemetry.
        """
        if not cls.is_heading(text):
            return None
        norm = text.strip().lower()
        if norm in PROTECTED_HEADINGS:
            return "PROTECTED_ACADEMIC_HEADING"
        if norm in KNOWN_HEADINGS:
            return "KNOWN_HEADING"
        with _learned_lock:
            if norm in _learned_headings:
                return "LEARNED_HEADING"
        if _is_section_label(text):
            return "SECTION_LABEL"
        if _is_title_case_heading(text):
            return "TITLE_CASE_HEADING"
        if _is_numbered_section(text):
            return "NUMBERED_SECTION"
        return "HEADING"


# ---------------------------------------------------------------------------
# Backward-compatible module-level aliases
# (entity_classifier.py imports these directly)
# ---------------------------------------------------------------------------

def are_all_words_capitalized(text: str) -> bool:
    """Legacy helper used by the old heading scoring code."""
    if not text:
        return False
    words = [w for w in re.findall(r'\b[a-zA-Z]+\b', text) if w]
    if not words:
        return False
    return all(w[0].isupper() for w in words)


def is_numbered_section(text: str) -> bool:
    """Legacy wrapper — delegates to internal _is_numbered_section()."""
    return _is_numbered_section(text)


def is_academic_heading(
    text: str,
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False,
    threshold: float = 40.0,
) -> bool:
    """Legacy wrapper — delegates to HeadingDetector.is_heading() + original score."""
    if HeadingDetector.is_heading(text):
        return True
    score = 0
    if is_standalone:
        score += 30
    if is_bold:
        score += 30
    if font_size > 12.0:
        score += 20
    if _is_numbered_section(text):
        score += 40
    if are_all_words_capitalized(text):
        score += 20
    return score >= threshold
