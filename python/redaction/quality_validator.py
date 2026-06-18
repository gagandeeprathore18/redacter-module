import re


class CandidateQualityValidator:

    MAX_WORDS = 15
    MAX_CHARS = 120
    MAX_SENTENCES = 1

    @staticmethod
    def count_sentences(text: str) -> int:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return len([s for s in sentences if s.strip()])

    @staticmethod
    def is_structural_content(text: str) -> bool:
        norm = text.lower().strip()

        structural_keywords = [
            "marking criteria",
            "rubric",
            "learning outcome",
            "grade descriptor",
            "assessment criteria",
            "pass status",
            "fail status",
            "grade threshold",
            "distinction",
            "merit",
            "referencing style",
            "achievement level",
            "academic integrity",
            "recommended reading",
            "assessment guidance",
            "submission guidance"
        ]

        if len(text) > 80 and any(
            kw in norm for kw in structural_keywords
        ):
            return True

        if text.count("\t") > 2:
            return True

        if text.count("\n") > 2:
            return True

        return False

    @staticmethod
    def is_instructional_content(text: str) -> bool:

        norm = text.lower().strip()

        instruction_phrases = [
            "the purpose of this assignment",
            "please ensure",
            "students must",
            "you are required",
            "work demonstrates",
            "academic integrity means",
            "this assignment requires",
            "in your submission",
            "you should",
            "you will need to",
            "support your analysis",
            "demonstrate your understanding"
        ]

        return any(
            phrase in norm
            for phrase in instruction_phrases
        )

    @classmethod
    def validate(
        cls,
        text: str,
        classification: str,
        score: float,
        reasons: list
    ) -> dict:

        word_count = len(text.split())
        char_count = len(text)
        sentence_count = cls.count_sentences(text)

        # ==================================
        # HARD FILTERS
        # NEVER ALLOW THESE TO REACH GPT
        # ==================================

        if word_count <= 3 and classification == "UNKNOWN":
            from redaction.human_name_validator import validate_human_name
            is_valid_name, _ = validate_human_name(text)
            if not is_valid_name:
                return {
                    "eligible_for_escalation": False,
                    "reason": "FRAGMENT_CONTENT",
                    "word_count": word_count
                }

        if cls.is_instructional_content(text):
            return {
                "eligible_for_escalation": False,
                "reason": "INSTRUCTIONAL_CONTENT",
                "word_count": word_count
            }

        if cls.is_structural_content(text):
            return {
                "eligible_for_escalation": False,
                "reason": "STRUCTURAL_CONTENT",
                "word_count": word_count
            }

        if char_count > cls.MAX_CHARS:
            return {
                "eligible_for_escalation": False,
                "reason": "LONG_TEXT",
                "word_count": word_count
            }

        if word_count > cls.MAX_WORDS:
            return {
                "eligible_for_escalation": False,
                "reason": "PARAGRAPH_CONTENT",
                "word_count": word_count
            }

        if sentence_count > cls.MAX_SENTENCES:
            return {
                "eligible_for_escalation": False,
                "reason": "MULTI_SENTENCE",
                "word_count": word_count
            }

        # ==================================
        # SAFE ENTITY BYPASS
        # ONLY AFTER QUALITY CHECKS
        # ==================================

        is_safe_entity = (
            classification in (
                "PERSON",
                "UNIVERSITY_ENTITY",
                "SUBMISSION_EVENT",
                "ACADEMIC_TITLE"
            )
            and (
                score >= 90
                or any("rule" in r.lower() for r in reasons)
                or any("learned" in r.lower() for r in reasons)
            )
        )

        if is_safe_entity:
            return {
                "eligible_for_escalation": True,
                "reason": None,
                "word_count": word_count
            }

        return {
            "eligible_for_escalation": True,
            "reason": None,
            "word_count": word_count
        }