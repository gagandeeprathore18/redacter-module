"""
Structural Content Detector  (Phase 2)
=======================================
Classifies document content that belongs to document STRUCTURE rather than
sensitive entities, using four categories:

    DOCUMENT_HEADER   – top-level module/assignment labels
    NAVIGATION_LABEL  – navigational / support section labels
    ACADEMIC_SECTION  – standard academic body sections
    REFERENCE_SECTION – bibliography / reading list sections

Usage:
    from redaction.structural_content_detector import StructuralContentDetector

    result = StructuralContentDetector.classify(text)
    # Returns:  {"category": "NAVIGATION_LABEL", "is_structural": True}
    # or:       {"category": None, "is_structural": False}
"""

import re

# ---------------------------------------------------------------------------
# Category keyword sets
# ---------------------------------------------------------------------------

_DOCUMENT_HEADER = {
    "assignment brief",
    "module information",
    "module overview",
    "course information",
    "course overview",
    "module handbook",
    "programme information",
    "programme overview",
    "key information",
    "important information",
    "general information",
    "assessment brief",
    "assessment overview",
    "unit information",
    "brief overview",
    "module details",
    "course details",
}

_NAVIGATION_LABEL = {
    "getting support",
    "your assignment",
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
    "student learning",
    "student services",
    "student resources",
    "academic support",
    "personal support",
    "wellbeing support",
    "disability support",
}

_ACADEMIC_SECTION = {
    "executive summary",
    "introduction",
    "background",
    "overview",
    "literature review",
    "theoretical framework",
    "conceptual framework",
    "research methodology",
    "methodology",
    "methods",
    "data collection",
    "data analysis",
    "findings",
    "results",
    "discussion",
    "analysis",
    "critical analysis",
    "evaluation",
    "reflection",
    "recommendations",
    "conclusion",
    "conclusions",
    "limitations",
    "future work",
    "future research",
    "appendix",
    "appendices",
    "glossary",
    "abstract",
    "preface",
    "foreword",
    "acknowledgements",
    "acknowledgments",
    "table of contents",
    "contents",
    "list of figures",
    "list of tables",
    "list of abbreviations",
    "learning outcomes",
    "intended learning outcomes",
    "module aims",
    "assessment criteria",
    "grading criteria",
    "marking criteria",
    "grade descriptors",
    "submission guidance",
    "research ethics",
    "ethical considerations",
    "academic integrity",
    "academic misconduct",
    "plagiarism policy",
}

_REFERENCE_SECTION = {
    "references",
    "reference list",
    "list of references",
    "bibliography",
    "recommended reading",
    "further reading",
    "reading list",
    "works cited",
    "sources",
    "harvard referencing",
    "apa referencing",
    "mla referencing",
    "cite them right",
}

# Map category name → set for lookup
_CATEGORY_MAP = {
    "DOCUMENT_HEADER":   _DOCUMENT_HEADER,
    "NAVIGATION_LABEL":  _NAVIGATION_LABEL,
    "ACADEMIC_SECTION":  _ACADEMIC_SECTION,
    "REFERENCE_SECTION": _REFERENCE_SECTION,
}

# Pre-built combined set for fast membership check
_ALL_STRUCTURAL = (
    _DOCUMENT_HEADER |
    _NAVIGATION_LABEL |
    _ACADEMIC_SECTION |
    _REFERENCE_SECTION
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class StructuralContentDetector:
    """
    Classifies text into structural content categories.
    Returns category name or None if not structural.
    """

    @classmethod
    def classify(cls, text: str) -> dict:
        """
        Returns:
            {
                "category": "NAVIGATION_LABEL" | "DOCUMENT_HEADER" |
                            "ACADEMIC_SECTION"  | "REFERENCE_SECTION" | None,
                "is_structural": True | False
            }
        """
        if not text or not text.strip():
            return {"category": None, "is_structural": False}

        norm = text.strip().lower()

        for cat_name, cat_set in _CATEGORY_MAP.items():
            if norm in cat_set:
                return {"category": cat_name, "is_structural": True}

        return {"category": None, "is_structural": False}

    @classmethod
    def is_structural(cls, text: str) -> bool:
        """Fast boolean check — True if text is structural content."""
        if not text:
            return False
        return text.strip().lower() in _ALL_STRUCTURAL

    @classmethod
    def get_category(cls, text: str) -> str | None:
        """Returns category name or None."""
        return cls.classify(text)["category"]
