def score_continuation_row(
    label_text: str,
    same_col_structure: bool = True,
    same_formatting: bool = True,
    adjacent_to_block: bool = True
) -> float:
    """
    Calculates continuation probability score for a table row based on signals:
    - Empty Label: +40
    - Same Column Structure: +20
    - Same Formatting: +20
    - Adjacent to Previous Block: +20
    """
    score = 0
    if not label_text or not label_text.strip():
        score += 40
    if same_col_structure:
        score += 20
    if same_formatting:
        score += 20
    if adjacent_to_block:
        score += 20
    return score

def is_continuation_row(
    label_text: str,
    same_col_structure: bool = True,
    same_formatting: bool = True,
    adjacent_to_block: bool = True,
    threshold: float = 80.0
) -> bool:
    score = score_continuation_row(label_text, same_col_structure, same_formatting, adjacent_to_block)
    return score >= threshold
