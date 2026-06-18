import re

_current_zone = None

def reset_protected_zone():
    global _current_zone
    _current_zone = None

def set_protected_zone(text: str):
    global _current_zone
    if not text:
        return
    norm = text.lower().strip()
    
    # Check learning outcomes section
    if "learning outcomes" in norm or "learning outcome" in norm or "grading criteria" in norm:
        _current_zone = "LEARNING_OUTCOMES_SECTION"
    # Check rubric section
    elif "rubric" in norm or "grading descriptor" in norm:
        _current_zone = "RUBRIC_SECTION"
    # Check reading list section
    elif "reading list" in norm or "reference list" in norm or "recommended reading" in norm or "bibliography" in norm:
        _current_zone = "READING_LIST_SECTION"
    # Check assessment guidance section
    elif "assessment guidance" in norm or "assessment brief" in norm or "guidance" in norm or "task" in norm:
        _current_zone = "ASSESSMENT_GUIDANCE_SECTION"
    # If it is a generic name or header label key, reset active zone
    elif len(norm) < 40 and any(h in norm for h in ["module leader", "module lead", "tutor", "submission location"]):
        _current_zone = None

def get_active_zone(text: str = "", context: str = "") -> str:
    global _current_zone
    if _current_zone:
        return _current_zone
        
    combined = (context + " " + text).lower()
    
    if "learning outcome" in combined or "grading criteria" in combined:
        return "LEARNING_OUTCOMES_SECTION"
    if "rubric" in combined or "grading descriptor" in combined:
        return "RUBRIC_SECTION"
    if "reading list" in combined or "reference list" in combined or "recommended reading" in combined or "bibliography" in combined:
        return "READING_LIST_SECTION"
    if "assessment guidance" in combined or "assessment brief" in combined or "guidance" in combined or "task" in combined:
        return "ASSESSMENT_GUIDANCE_SECTION"
        
    return None
