def calculate_confidence_score(
    exact_match: bool = False,
    fuzzy_match: bool = False,
    continuation_row: bool = False,
    adjacent_content: bool = False
) -> float:
    """
    Calculates confidence score based on signals:
    - exact_match: +60
    - fuzzy_match: +40
    - continuation_row: +20
    - adjacent_content: +20
    """
    score = 0
    if exact_match:
        score += 60
    if fuzzy_match:
        score += 40
    if continuation_row:
        score += 20
    if adjacent_content:
        score += 20
    return score

def should_redact(
    exact_match: bool = False,
    fuzzy_match: bool = False,
    continuation_row: bool = False,
    adjacent_content: bool = False,
    threshold: float = 70.0
) -> bool:
    score = calculate_confidence_score(exact_match, fuzzy_match, continuation_row, adjacent_content)
    return score >= threshold

def evaluate_human_name(
    base_name_score: float,
    heading_detected: bool = False,
    has_academic_keyword: bool = False,
    is_numbered: bool = False
) -> tuple:
    """
    Evaluates final human name score with heading and academic exclusions:
    - Capitalized phrase base: e.g. +20 (implicit from classifier)
    - Heading detected penalty: -30
    - Academic keyword/exclusion penalty: -40
    - Numbered section penalty: -50
    Returns: (final_score, should_redact)
    """
    # Start with base score from name classifier
    score = base_name_score
    
    if heading_detected:
        score -= 30
    if has_academic_keyword:
        score -= 40
    if is_numbered:
        score -= 50
        
    # Redaction threshold is 50+ (e.g. two-word name +20 and module leader context +30 = 50 -> redact)
    return score, (score >= 50)
