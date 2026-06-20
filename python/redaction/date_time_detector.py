import re

# Compile patterns as requested by the migration strategy (case-insensitive)
NUMERIC_DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.IGNORECASE)

ORDINAL_DATE_PATTERN = re.compile(
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4}\b",
    re.IGNORECASE
)

MONTH_FIRST_DATE_PATTERN = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b",
    re.IGNORECASE
)

TIME_24H_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b", re.IGNORECASE)

TIME_AMPM_PATTERN = re.compile(r"\b\d{1,2}(?::|\.)?\d{0,2}\s*(?:am|pm)\b", re.IGNORECASE)

MILITARY_TIME_PATTERN = re.compile(r"\b\d{3,4}\s*(?:hours|hrs?)\b", re.IGNORECASE)

DATE_PATTERNS = [NUMERIC_DATE_PATTERN, ORDINAL_DATE_PATTERN, MONTH_FIRST_DATE_PATTERN]
TIME_PATTERNS = [TIME_24H_PATTERN, TIME_AMPM_PATTERN, MILITARY_TIME_PATTERN]

CONNECTOR_PATTERN = re.compile(r"^\s*(?:at|on|by|before|after|no\s+later\s+than|not\s+later\s+than|,|@|\s)*\s*$", re.IGNORECASE)

def find_date_time_spans(text: str) -> list:
    """
    Finds all date, time, and date-time combinations in the text.
    Returns a sorted list of tuples: (start_char_idx, end_char_idx, matched_substring, type)
    where type is 'DATE' or 'TIME'. Spans with both dates and times are classified as 'DATE'.
    """
    if not text:
        return []

    raw_matches = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            raw_matches.append((match.start(), match.end(), "DATE"))

    for pattern in TIME_PATTERNS:
        for match in pattern.finditer(text):
            raw_matches.append((match.start(), match.end(), "TIME"))

    if not raw_matches:
        return []

    # Sort matches by start position
    raw_matches.sort(key=lambda x: x[0])

    # 1. Merge overlapping or directly adjacent spans
    merged = []
    for current in raw_matches:
        if not merged:
            merged.append(current)
        else:
            prev_start, prev_end, prev_type = merged[-1]
            curr_start, curr_end, curr_type = current
            if curr_start <= prev_end:
                # Overlap or contiguous
                new_type = "DATE" if (prev_type == "DATE" or curr_type == "DATE") else "TIME"
                merged[-1] = (prev_start, max(prev_end, curr_end), new_type)
            else:
                merged.append(current)

    # 2. Merge spans separated only by connector words/characters (e.g. "by 5PM", "at 4:00")
    final_spans = []
    for start, end, m_type in merged:
        if not final_spans:
            final_spans.append((start, end, m_type))
        else:
            prev_start, prev_end, prev_type = final_spans[-1]
            between_text = text[prev_end:start]
            if CONNECTOR_PATTERN.match(between_text):
                # Merge them
                new_type = "DATE" if (prev_type == "DATE" or m_type == "DATE") else "TIME"
                final_spans[-1] = (prev_start, end, new_type)
            else:
                final_spans.append((start, end, m_type))

    # Convert to list of (start, end, matched_text, type)
    return [(start, end, text[start:end], m_type) for start, end, m_type in final_spans]
