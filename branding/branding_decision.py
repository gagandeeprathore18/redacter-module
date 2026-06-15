from .university_matcher import UniversityMatcher

class BrandingDecisionEngine:
    def __init__(self):
        self.matcher = UniversityMatcher()
        self.threshold = 70
        
    def evaluate_image(self, img_meta: dict, ocr_text: str) -> tuple[bool, int, dict]:
        """
        Evaluates an image and returns: (should_remove, score, breakdown_dict)
        """
        score = 0
        breakdown = {}
        
        # 1. Location Heuristics
        loc = img_meta.get("location", "body")
        page = img_meta.get("page", 1)
        width = img_meta.get("width", 0)
        height = img_meta.get("height", 0)
        repeats = img_meta.get("repeat_count", 1)
        
        # Header (+40)
        if loc == "header":
            score += 40
            breakdown["header_location"] = 40
            
        # Footer (+40)
        elif loc == "footer":
            score += 40
            breakdown["footer_location"] = 40
            
        # First Page (+20)
        if page == 1:
            score += 20
            breakdown["first_page"] = 20
            
        # Small Image (< 500x500px, +10)
        if width > 0 and height > 0 and width < 500 and height < 500:
            score += 10
            breakdown["small_image"] = 10
            
        # Repeated Image (+20)
        if repeats > 1:
            score += 20
            breakdown["repeated_image"] = 20
            
        # 2. OCR Database Scores
        univ_score, keyword_score = self.matcher.compute_scores(ocr_text)
        
        if univ_score > 0:
            score += univ_score
            breakdown["university_match"] = univ_score
            
        if keyword_score > 0:
            score += keyword_score
            breakdown["keyword_match"] = keyword_score
            
        should_remove = score >= self.threshold
        return should_remove, score, breakdown
