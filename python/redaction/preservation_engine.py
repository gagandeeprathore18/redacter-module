import re
from redaction.rubric_detector import is_rubric_text

PRESERVE_PATTERNS = [
    "learning outcome",
    "assessment rubric",
    "grading criteria",
    "research methodology",
    "research methods",
    "literature review",
    "reference list",
    "recommended reading",
    "research ethics",
    "academic integrity",
    "harvard referencing",
    "findings and analysis",
    "recommendations and conclusion",
]

BIBLIOGRAPHIC_PATTERNS = [
    r'\bOxford University Press\b',
    r'\bRoutledge\b',
    r'\bJournal\b',
    r'\bVol\.\s*\d+',
    r'\bIssue\s*\d+',
    r'\bpp\.\s*\d+',
    r'\b\([12]\d{3}\)',  # e.g. (2021)
    r'\b[A-Z][a-z]+,\s*[A-Z]\.',  # e.g. Smith, J.
]

CATEGORY_KEYWORDS = {
    "LEARNING_OUTCOME": ["learning outcomes", "learning outcome", "lo1", "lo2", "lo3", "lo4", "alignment to uca", "generic grading descriptor"],
    "RUBRIC_CONTENT": ["module assessment rubric", "pass = 40-49%", "excellent pass = 70-89%", "research topic and context", "research aim and methodology"],
    "ASSESSMENT_GUIDANCE": ["what your presentation should include", "findings and analysis", "recommendations and conclusion"],
    "RESEARCH_GUIDANCE": ["research methods", "research design", "sampling approach", "data collection", "literature review"],
    "READING_LIST": ["recommended reading", "reference list", "harvard referencing", "bell et al.", "research methods in applied settings"],
    "ACADEMIC_POLICY": ["academic integrity", "research ethics", "use of artificial intelligence", "mitigating circumstances"]
}

class PreservationEngine:
    
    @staticmethod
    def is_title_case(text: str) -> bool:
        if not text:
            return False
        # Remove digits and special characters
        cleaned = re.sub(r'[^a-zA-Z\s]', '', text).strip()
        words = [w for w in cleaned.split() if len(w) > 2]
        if not words:
            return False
        return all(w[0].isupper() for w in words)

    @classmethod
    def is_section_header(
        cls,
        text: str,
        context: str = "",
        is_bold: bool = False,
        font_size: float = 0.0,
        is_standalone: bool = False
    ) -> bool:
        cleaned = text.strip()
        if not cleaned:
            return False
            
        # Title Case + (Bold or Large Font or Standalone)
        if cls.is_title_case(cleaned):
            if is_bold or font_size >= 12.0 or is_standalone:
                return True
                
        # Common Section Labels Check
        norm = cleaned.lower()
        section_labels = [
            "learning outcomes",
            "module assessment rubric",
            "research topic and context",
            "generic grading criteria",
            "assessment criteria"
        ]
        if any(lbl in norm for lbl in section_labels):
            return True
            
        return False

    @staticmethod
    def is_bibliographic_entry(text: str) -> bool:
        if not text:
            return False
        # Check explicit citation/publisher patterns
        for p in BIBLIOGRAPHIC_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                return True
        # Check citation "et al"
        if re.search(r'\b[A-Z][a-zA-Z]*\s+et\s+al\b', text):
            return True
        return False

    @classmethod
    def check_preservation(
        cls,
        text: str,
        context: str = "",
        is_bold: bool = False,
        font_size: float = 0.0,
        is_standalone: bool = False
    ) -> dict:
        """
        Main interface to check if a candidate should be preserved.
        Returns: dict with "action": "PRESERVE", "reason": "ACADEMIC_CONTENT" / "PROTECTED_SECTION" / "SECTION_HEADING"
        or None.
        """
        if not text:
            return None
            
        if is_sensitive_entity(text, context):
            return None
            
        norm = text.lower().strip()
        
        # 0. Explicit Protected Section check (to match deterministic classifications)
        protected_sections = {
            "recommended reading",
            "reference list",
            "learning outcomes",
            "academic integrity",
            "confidentiality"
        }
        if norm in protected_sections:
            return {"action": "PRESERVE", "reason": "PROTECTED_SECTION"}
        
        # 1. Structural Section Detection
        if cls.is_section_header(text, context, is_bold, font_size, is_standalone):
            return {"action": "PRESERVE", "reason": "SECTION_HEADING"}
            
        # 2. Reading List / Bibliographic Entry Protection
        if cls.is_bibliographic_entry(text):
            return {"action": "PRESERVE", "reason": "ACADEMIC_CONTENT"}
            
        # 3. Rubric Text Protection
        if is_rubric_text(text, context):
            # Rubric protection applies UNLESS the text is a sensitive entity
            from redaction.rubric_detector import RUBRIC_PATTERN
            # We check if it is a sensitive entity
            if not is_sensitive_entity(text, context):
                return {"action": "PRESERVE", "reason": "ACADEMIC_CONTENT"}
                
        # 4. Hard Preserve Patterns
        for pat in PRESERVE_PATTERNS:
            if pat in norm:
                return {"action": "PRESERVE", "reason": "ACADEMIC_CONTENT"}
                
        # 5. Category Keyword Check
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in norm:
                    # Double check if it is not sensitive before preserving
                    if not is_sensitive_entity(text, context):
                        return {"action": "PRESERVE", "reason": "ACADEMIC_CONTENT"}
                        
        return None

def is_sensitive_entity(text: str, context: str = "") -> bool:
    if not text:
        return False
    # Check metadata field label
    try:
        from redaction.metadata_field_detector import is_metadata_field
        if is_metadata_field(text):
            return True
    except Exception:
        pass
    # Check email, phone, student id
    from redact_engine import EMAIL_PATTERN, PHONE_PATTERN, STUDENT_ID_PATTERN
    if EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text) or STUDENT_ID_PATTERN.search(text):
        return True
        
    # Check if it looks like a person's name
    try:
        from redaction.human_name_validator import validate_human_name
        from redaction.human_name_classifier import score_human_name
        is_valid_name, _ = validate_human_name(text)
        if is_valid_name and score_human_name(text, context) >= 70:
            return True
    except Exception:
        pass
        
    return False
