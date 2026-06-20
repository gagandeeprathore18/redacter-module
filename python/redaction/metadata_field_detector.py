import re

METADATA_LABELS = {
    "submission deadline",
    "submission date",
    "assessment submission date",
    "date of submission",
    "feedback release date",
    "target feedback date",
    "module lead",
    "module leader",
    "tutor name",
    "assessor",
    "internal verifier",
    "student id",
    "student number",
    "registration number",
    "module code",
    "academic year",
    "programme code",
    "programme title",
    "course code",
    # Additional administrative labels
    "submission location",
    "submit to",
    "submission point",
    "submission portal",
    "submission platform",
    "submission link",
    "submission method",
    "submission box",
    "submission folder",
    "submission area",
    "submission mode",
    "submission type",
    "submission system",
    "submission details",
    "submit via",
    "submit through",
    "submit using",
    "submit on",
    "how to submit",
    "where to submit",
    "online submission",
    "e-submission",
    "upload location",
    "upload link",
    "upload portal",
    "upload to",
    "provisional marks",
    "written feedback",
    "target feedback",
    "target feedback time",
    "target feedback time and date",
    "feedback date",
    "return date",
    # Missing labels from spec (Priority 7)
    "date of approval",
    "semester",
    "module title",
    "credit value",
    "brief released",
    "module code",
    "date of issue",
    "issued by",
    "approved by",
    "version",
    "level",
    "awarding body",
    "qualification title",
    "qualification level",

}

METADATA_LABELS_TO_KEEP = {
    "semester",
    "level",
    "version",
    "module title",
    "credit value",
    "qualification title",
    "qualification level",
    "awarding body",
    "brief released",
    "module code"
}

def is_metadata_field_to_keep(text: str) -> bool:
    if not text:
        return False
    norm_text = text.lower().strip()
    if norm_text in METADATA_LABELS_TO_KEEP:
        return True
    if norm_text.endswith(":"):
        stripped = norm_text[:-1].strip()
        if stripped in METADATA_LABELS_TO_KEEP:
            return True
    if ":" in norm_text:
        prefix = norm_text.split(":", 1)[0].strip()
        if prefix in METADATA_LABELS_TO_KEEP:
            return True
    for label in METADATA_LABELS_TO_KEEP:
        if re.match(rf'\b{re.escape(label)}\b', norm_text):
            return True
    return False

def is_metadata_field(text: str) -> bool:
    if not text:
        return False
    norm_text = text.lower().strip()
    if norm_text in METADATA_LABELS:
        return True
    if norm_text.endswith(":"):
        stripped = norm_text[:-1].strip()
        if stripped in METADATA_LABELS:
            return True
    if ":" in norm_text:
        prefix = norm_text.split(":", 1)[0].strip()
        if prefix in METADATA_LABELS:
            return True
    for label in METADATA_LABELS:
        if re.match(rf'\b{re.escape(label)}\b', norm_text):
            return True
    return False
