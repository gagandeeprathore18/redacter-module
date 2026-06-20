from redaction.academic_title_detector import detect_academic_title

def validate_human_name(text: str) -> tuple:
    """
    Validates if a candidate is actually a human name and does not contain academic terms or stop words.
    Returns: (is_valid, reason)
    """
    if not text:
        return False, "empty_text"
        
    PERSON_STOPWORDS = {
        # Original stopwords
        "study",
        "hours",
        "guided",
        "scheduled",
        "resources",
        "academic",
        "appeals",
        "presentation",
        "deadline",
        "module",
        "research",
        "questions",
        # Extended academic stopwords (Priority 2)
        "learning",
        "analysis",
        "assessment",
        "criteria",
        "outcomes",
        "proposal",
        "methodology",
        "ethics",
        "findings",
        "recommendations",
        "literature",
        "independent",
        "teaching",
        "credit",
        "value",
        "semester",
        "grading",
        "rubric",
        "descriptor",
        "distinction",
        "merit",
        "referencing",
        "discussion",
        "conclusion",
        "framework",
        "data",
        "collection",
        "objectives",
        "aim",
        "aims",
        "brief",
        "guidance",
        "integrity",
        "misconduct",
        "policy",
    }
    
    import re as _re
    words = {w.lower() for w in _re.split(r'[\s\-_]+', text) if w}
    intersect = words.intersection(PERSON_STOPWORDS)
    if intersect:
        return False, f"stopword_detected: {list(intersect)[0]}"
        
    is_academic, matched_term = detect_academic_title(text)
    if is_academic:
        return False, f"academic_term_detected: {matched_term}"
        
    return True, None

