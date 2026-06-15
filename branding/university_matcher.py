import json
import os
import re

class UniversityMatcher:
    def __init__(self):
        # Load databases
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        univ_path = os.path.join(curr_dir, "university_db.json")
        keywords_path = os.path.join(curr_dir, "branding_keywords.json")
        
        try:
            with open(univ_path, "r") as f:
                self.universities = json.load(f).get("universities", [])
        except Exception:
            self.universities = []
            
        try:
            with open(keywords_path, "r") as f:
                self.keywords = json.load(f)
        except Exception:
            self.keywords = {"strong": [], "medium": []}
            
    def compute_scores(self, ocr_text: str) -> tuple[int, int]:
        """
        Calculates matching scores.
        Returns a tuple: (university_score, keyword_score)
        """
        if not ocr_text:
            return 0, 0
            
        ocr_text_lower = ocr_text.lower()
        
        # 1. Match Universities Name & Aliases
        univ_score = 0
        for univ in self.universities:
            name = univ.get("name", "").lower()
            aliases = [a.lower() for a in univ.get("aliases", [])]
            
            # Exact Match (+60)
            # Use word boundaries or substring search depending on requirements
            if name in ocr_text_lower:
                univ_score = max(univ_score, 60)
                
            # Alias Match (+40)
            for alias in aliases:
                # Match alias as a whole word to prevent partial matches like "ox" matching in "box"
                pattern = rf'\b{re.escape(alias)}\b'
                if re.search(pattern, ocr_text_lower):
                    univ_score = max(univ_score, 40)
                    
        # 2. Match Branding Keywords
        keyword_score = 0
        
        # Strong Keywords (+20 max)
        for kw in self.keywords.get("strong", []):
            if kw.lower() in ocr_text_lower:
                keyword_score += 20
                break # Cap strong keyword contribution at 20
                
        # Medium Keywords (+10 max)
        for kw in self.keywords.get("medium", []):
            if kw.lower() in ocr_text_lower:
                keyword_score += 10
                break # Cap medium keyword contribution at 10
                
        return univ_score, keyword_score
