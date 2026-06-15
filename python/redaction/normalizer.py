import re

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation: :, ;, ,, .
    text = re.sub(r'[:;,\.]', '', text)
    # Collapse multiple spaces, tabs, and line breaks to a single space
    text = re.sub(r'[\s\n\t\r]+', ' ', text)
    return text.strip()
