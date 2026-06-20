"""
Context Protection Layer
========================
Guards against two types of content destruction:

1. Parent Block Protection:
   If a candidate belongs to a parent block of > 30 words AND is not
   a definitively sensitive entity type, preserve it.

2. Fragment Protection:
   If a candidate has <= 4 words or <= 30 chars AND its classification
   is ambiguous (UNKNOWN, ACADEMIC_CONTENT, ACADEMIC_TITLE, BUSINESS_FIELD),
   preserve it to prevent partial sentence destruction.
"""

# Classifications that are always allowed to be redacted regardless of context
ALWAYS_REDACT_CLASSES = {
    "PERSON",
    "METADATA_FIELD",
    "SUBMISSION_EVENT",
    "UNIVERSITY_BRANDING",
    "UNIVERSITY_ENTITY",
    "EMAIL",
    "PHONE",
    "STUDENT_ID",
    "POSTAL_CODE",
}

# Classifications that should be preserved if they appear as short fragments
PRESERVE_IF_FRAGMENT = {
    "UNKNOWN",
    "ACADEMIC_CONTENT",
    "ACADEMIC_TITLE",
    "BUSINESS_FIELD",
    "SECTION_HEADING",
    "PROTECTED_SECTION",
}


def is_parent_block_protected(word_count: int, classification: str) -> bool:
    """
    Returns True if the candidate should be preserved because it belongs to
    a large parent block (> 30 words) and is not a definitively sensitive type.

    This prevents sub-phrase extraction from destroying academic paragraphs.
    """
    if word_count > 30 and classification not in ALWAYS_REDACT_CLASSES:
        return True
    return False


def is_fragment_protected(word_count: int, char_count: int, classification: str) -> bool:
    """
    Returns True if the candidate should be preserved because it is a very
    short fragment (<=4 words or <=30 chars) with an ambiguous classification.

    This prevents destroying partial sentences like:
        "Research Ethics: You must adhere to th n"
        "By completing this project, you will develop i"
    """
    if classification in PRESERVE_IF_FRAGMENT:
        if word_count <= 4 or char_count <= 30:
            return True
    return False


def should_preserve_by_context(
    text: str,
    classification: str,
    parent_word_count: int = 0
) -> tuple:
    """
    Main interface. Checks both protection rules.

    Returns: (should_preserve: bool, reason: str)
    """
    if not text:
        return False, ""

    word_count = len(text.split())
    char_count = len(text)

    if is_parent_block_protected(parent_word_count or word_count, classification):
        return True, "PARENT_BLOCK_PROTECTION"

    if is_fragment_protected(word_count, char_count, classification):
        return True, "FRAGMENT_PROTECTION"

    return False, ""
