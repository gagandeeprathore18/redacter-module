from redaction.academic_title_detector import detect_academic_title

def validate_human_name(text: str) -> tuple:
    """
    Validates if a candidate is actually a human name and does not contain academic terms.
    Returns: (is_valid, reason)
    """
    if not text:
        return False, "empty_text"
        
    is_academic, matched_term = detect_academic_title(text)
    if is_academic:
        return False, f"academic_term_detected: {matched_term}"
        
    return True, None
