def get_sensitivity_score(classification: str) -> int:
    """
    Returns the sensitivity score for a given classification category.
    Only categories scoring >= 70 are allowed to be redacted.
    """
    scores = {
        "PERSON": 95,
        "EMAIL": 100,
        "STUDENT_ID": 100,
        "PHONE": 100,
        "UNIVERSITY_BRANDING": 80,
        "UNIVERSITY_ENTITY": 80,
        "SUBMISSION_EVENT": 75,
        "BUSINESS_FIELD": 50,
        "ACADEMIC_TITLE": 0,
        "SECTION_HEADING": 0,
        "PROTECTED_SECTION": 0,
        "ACADEMIC_CONTENT": 0,
        "UNKNOWN": 0
    }
    return scores.get(classification, 0)
