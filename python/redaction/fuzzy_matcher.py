from rapidfuzz import fuzz
from redaction.normalizer import normalize_text

def get_similarity_score(text1: str, text2: str, partial: bool = False) -> float:
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    if not norm1 or not norm2:
        return 0.0
    if partial:
        return fuzz.partial_ratio(norm2, norm1)
    return fuzz.ratio(norm1, norm2)

def is_fuzzy_match(text: str, target: str, threshold: float = 85.0, partial: bool = False) -> bool:
    score = get_similarity_score(text, target, partial=partial)
    return score >= threshold
