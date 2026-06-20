import re

RUBRIC_KEYWORDS = [
    r'pass\s*=\s*\d+-\d+%',
    r'good\s+pass\s*=\s*\d+-\d+%',
    r'excellent\s+pass\s*=\s*\d+-\d+%',
    r'fail\s*=\s*\d+-\d+%',
    r'fail\s*learning\s+outcomes\s+have\s+not\s+been\s+met',
    r'learning\s+outcomes\s+have\s+been\s+met',
    r'learning\s+outcomes\s+have\s+been\s+exceeded',
    r'categorical\s+mark\s+and\s+grade',
    r'pass\s+status',
    r'marginal\s+fail',
    r'grade\s+descriptor',
    r'generic\s+grading',
    r'assessment\s+criteria',
    r'knowledge\s+and\s+understanding',
    r'analysis,\s+creativity\s+and\s+problem-solving',
    r'research/referencing',
    r'written\s+english',
    r'presentation\s+and\s+structure',
    # Priority 5 expanded rubric terms
    r'learning\s+outcome',
    r'grading\s+criteria',
    r'research\s+and\s+analysis',
    r'engaging\s+with\s+practice',
    r'realisation\s+and\s+communication',
    r'grade\s+descriptors',
    r'marking\s+criteria',
    r'\bdistinction\b',
    r'\bmerit\b',
    r'fail\s+criteria',
    r'pass\s+criteria',
]


RUBRIC_PATTERN = re.compile('|'.join(RUBRIC_KEYWORDS), re.IGNORECASE)

def is_rubric_table(table_rows_text: list) -> bool:
    """
    Given a list of strings representing the text in a table's rows/cells,
    determines if the table is a rubric table.
    """
    hits = 0
    for text in table_rows_text:
        if not text:
            continue
        if RUBRIC_PATTERN.search(text):
            hits += 1
    return hits >= 2

def is_rubric_text(text: str, context: str = "") -> bool:
    """
    Checks if a candidate's text or context matches rubric patterns.
    """
    if not text:
        return False
    norm_text = text.lower().strip()
    norm_context = context.lower().strip()
    
    # Check text directly
    if RUBRIC_PATTERN.search(norm_text):
        return True
        
    # Check generic grade boundaries: e.g. "40-49%", "70-89%"
    if re.search(r'\b\d+-\d+%\b', norm_text):
        return True
        
    # If context is clearly a rubric
    if "rubric" in norm_context or "grading criteria" in norm_context or "grading descriptor" in norm_context:
        # Check if text looks like rubric text
        if any(w in norm_text for w in ["pass", "fail", "learning", "outcomes", "criteria", "grade", "mark"]):
            return True
            
    return False
