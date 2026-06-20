import re

TITLE_ABBREVS = re.compile(
    r'\b(Prof|Dr|Mr|Mrs|Ms|Rev|Sr|Jr|Lt|Capt|Col|Gen|Sgt|Cpl|Maj|St|Gov|Pres|Assoc|Adj)\.',
    re.IGNORECASE
)

def count_sentences(text: str) -> int:
    sanitised = TITLE_ABBREVS.sub(lambda m: m.group(0).replace('.', '\x00'), text.strip())
    sentences = re.split(r'(?<=[.!?])\s+', sanitised)
    return len([s for s in sentences if s.strip()])

def is_paragraph(text: str) -> bool:
    """
    Returns True if the text matches paragraph filter criteria.
    """
    if not text:
        return False
        
    cleaned = text.strip()
    words = cleaned.split()
    word_count = len(words)
    char_count = len(cleaned)
    sentence_count = count_sentences(cleaned)
    
    # Rule 1 - Word Count
    if word_count > 15:
        return True
        
    # Rule 2 - Multiple Sentences
    if sentence_count > 1:
        return True
        
    # Rule 3 - Character Count
    if char_count > 120:
        return True
        
    # Rule 4 - Academic Paragraph Indicators
    academic_indicators = [
        "demonstrates",
        "learning outcomes",
        "knowledge and understanding",
        "critical evaluation",
        "reflection",
        "research methodology"
    ]
    norm = cleaned.lower()
    if word_count > 8:
        if any(ind in norm for ind in academic_indicators):
            return True
            
    return False
