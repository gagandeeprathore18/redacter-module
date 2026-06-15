import re

TITLE_PREFIXES = ["dr", "prof", "professor", "mr", "mrs", "ms"]
CONTEXT_KEYWORDS = ["module leader", "module lead", "lead", "tutor", "approved by", "internal approval", "lecturer", "assessor", "verifier", "moderator", "student name", "name", "signed", "signature", "author"]

def score_human_name(text: str, context: str = "") -> float:
    """
    Evaluates probability of a string being a human name:
    - Two-word name: +20
    - Three-word name: +25
    - Title Prefix: +30
    - Context keywords proximity: +30
    """
    score = 0
    if not text:
        return score
        
    import re as _re
    text_clean = text.strip()
    # Split on both whitespace AND hyphens so "Smith-Jones" counts as 2 words
    words = [w for w in _re.split(r'[\s\-]+', text_clean) if w]
    if not words:
        return score
        
    # Check Title Prefix first
    first_word_lower = words[0].lower().replace('.', '')
    has_prefix = False
    if first_word_lower in TITLE_PREFIXES:
        score += 30
        has_prefix = True
        # Strip the prefix to evaluate word count of actual name
        words = words[1:]
        
    # Word counts on the remaining part of the name
    if len(words) == 2:
        score += 20
    elif len(words) >= 3:
        score += 25
        
    # Context keywords (appears after / nearby)
    if context:
        context_lower = context.lower()
        for kw in CONTEXT_KEYWORDS:
            if kw in context_lower:
                score += 30
                break
                
    return score
