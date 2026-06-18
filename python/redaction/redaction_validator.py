import re

def validate_redaction(text: str, classification: str) -> bool:
    """
    Validates a redaction decision before finalizing.
    Returns True if the redaction is valid and should proceed.
    Returns False if the redaction should be rejected (preserved).
    """
    if not text:
        return False
        
    cleaned = text.strip()
    words = cleaned.split()
    word_count = len(words)
    
    # Reject if word_count > 8 and classification is ACADEMIC_CONTENT
    if word_count > 8 and classification == "ACADEMIC_CONTENT":
        return False
        
    # Reject if contains multiple sentences
    from redaction.quality_validator import CandidateQualityValidator
    if CandidateQualityValidator.count_sentences(cleaned) > 1:
        return False
        
    # Reject if contains academic keywords:
    academic_keywords = ["theories", "frameworks", "research", "methodology", "analysis", "findings", "literature"]
    norm = cleaned.lower()
    if any(kw in norm for kw in academic_keywords):
        return False
        
    return True
