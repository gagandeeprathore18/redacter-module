import re

NUMBERED_SECTION_PATTERN = re.compile(r'^\d+(?:\.\d+)*\.?\s+[A-Z]')

MONTHS = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"
}

def is_numbered_section(text: str) -> bool:
    if not text:
        return False
    cleaned = text.strip()
    match = NUMBERED_SECTION_PATTERN.search(cleaned)
    if not match:
        return False
    # Check if the word following the number prefix is a month name (which indicates it is a date)
    word_match = re.search(r'[A-Za-z]+', cleaned[match.end() - 1:])
    if word_match:
        word = word_match.group(0).lower()
        if word in MONTHS:
            return False
    return True

def are_all_words_capitalized(text: str) -> bool:
    if not text:
        return False
    words = [w for w in re.findall(r'\b[a-zA-Z]+\b', text) if w]
    if not words:
        return False
    return all(w[0].isupper() for w in words)

def calculate_heading_score(
    text: str,
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False
) -> float:
    """
    Evaluates probability of a string being a section heading:
    - Standalone Paragraph: +30
    - Entire Paragraph Bold: +30
    - Larger Font Size (>12pt): +20
    - Numbered Section: +40
    - All Words Capitalized: +20
    """
    score = 0
    if not text:
        return score
        
    if is_standalone:
        score += 30
    if is_bold:
        score += 30
    if font_size > 12.0:
        score += 20
    if is_numbered_section(text):
        score += 40
    if are_all_words_capitalized(text):
        score += 20
        
    return score

def is_academic_heading(
    text: str,
    is_bold: bool = False,
    font_size: float = 0.0,
    is_standalone: bool = False,
    threshold: float = 40.0
) -> bool:
    score = calculate_heading_score(text, is_bold, font_size, is_standalone)
    return score >= threshold
