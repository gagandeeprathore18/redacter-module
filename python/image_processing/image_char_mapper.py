class ImageCharMapper:
    def __init__(self, ocr_words: list):
        self.ocr_words = ocr_words
        self.full_text = ""
        self.char_map = []  # list of dicts: {"char": str, "bbox": [x, y, w, h]}

        self._build_char_map()

    def _build_char_map(self):
        full_text_list = []
        for idx, word in enumerate(self.ocr_words):
            word_text = word.text
            x, y, w, h = word.bbox
            n_chars = len(word_text)
            
            if n_chars > 0:
                char_w = w / n_chars
                for i, char in enumerate(word_text):
                    char_bbox = [x + i * char_w, y, char_w, h]
                    self.char_map.append({
                        "char": char,
                        "bbox": char_bbox
                    })
                    full_text_list.append(char)
            
            # Add space between words
            if idx < len(self.ocr_words) - 1:
                self.char_map.append({
                    "char": " ",
                    "bbox": None
                })
                full_text_list.append(" ")
                
        self.full_text = "".join(full_text_list)

    def get_bbox_for_span(self, start_idx: int, end_idx: int) -> list:
        """
        Calculates the bounding box that covers characters from start_idx to end_idx (exclusive).
        Returns [x, y, w, h] or None.
        """
        sub_map = self.char_map[start_idx:end_idx]
        valid_bboxes = [item["bbox"] for item in sub_map if item["bbox"] is not None]
        
        if not valid_bboxes:
            return None
            
        x0 = min(b[0] for b in valid_bboxes)
        y0 = min(b[1] for b in valid_bboxes)
        x1 = max(b[0] + b[2] for b in valid_bboxes)
        y1 = max(b[1] + b[3] for b in valid_bboxes)
        
        return [x0, y0, x1 - x0, y1 - y0]
