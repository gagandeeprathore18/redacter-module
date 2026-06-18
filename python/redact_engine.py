import re
import os
import json
from PIL import Image
import imagehash
import io

# Load domain database
DOMAINS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logos', 'domains.json')
LOGOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logos')

try:
    with open(DOMAINS_FILE, 'r') as f:
        UNIVERSITY_DOMAINS = json.load(f)
except Exception:
    UNIVERSITY_DOMAINS = []

# Regex patterns
STUDENT_ID_PATTERN = re.compile(r'\b(?:ST|REG|APP|ROLL)\d+\b', re.IGNORECASE)
EMAIL_PATTERN = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
PHONE_PATTERN = re.compile(
    r'(?:'
    r'\+?\d{1,4}[-.\s]?(?:\(\d{1,4}\)|\d{1,4})[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    r'|\b\d{5}[-.\s]?\d{6}\b'
    r'|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
    r'|\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b'
    r')',
    re.IGNORECASE
)
URL_PATTERN = re.compile(r'\b(?:https?://|www\.)[a-zA-Z0-9-._~:/?#\[\]@!$&\'()*+,;=]+\b', re.IGNORECASE)
POSTAL_CODE_PATTERN = re.compile(r'\b\d{5}(?:-\d{4})?\b|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b', re.IGNORECASE)

# Name patterns
NAME_KEYWORDS = [
    r'Name/Signed', r'Name\s*/\s*Signed',
    r'(?<!\bModule\s)(?<!\bCourse\s)(?<!\bProgramme\s)(?<!\bTask\s)(?<!\bFile\s)(?<!\bProject\s)(?<!\bBrand\s)Name',
    r'Signed', r'Signature',
    r'Module\s+lead(?:er)?', r'Tutor', r'Lecturer', r'Professor', r'Author',
    r'Student', r'Assessor', r'Internal\s+Verifier', r'Verifier',
    r'Moderator', r'Internal\s+Moderator', r'External\s+Examiner',
    r'Examiner', r'Lead(?:er)?'
]

NAME_PROXIMITY_PATTERN = re.compile(
    r'\b(?i:' + '|'.join(NAME_KEYWORDS) + r')(?:\'s|s)?\b[:\s\-]*'
    r'([A-Z][a-zA-Z]*(?:\.[A-Z]*)?(?:[ \t]+|-)[A-Z][a-zA-Z]+(?:[ \t]+[A-Z][a-zA-Z]+)*)'
)

NAME_PATTERN = re.compile(
    r'\b[A-Z][a-zA-Z]*(?:\.[A-Z]*)?(?:[ \t]+|-)[A-Z][a-zA-Z]+(?:[ \t]+[A-Z][a-zA-Z]+)*\b'
)

TABLE_ROW_NAME_KEYWORD_PATTERN = re.compile(
    r'(?:'
    r'^\s*Name\s*:?$'
    r'|\b(?:Student|Tutor|Assessor|Lecturer|Full|Your|First|Last|Family|Module\s+lead(?:er)?)(?:\'s)?\s+Name\b'
    r'|\b(?:Signed|Signature|Tutor|Lecturer|Professor|Author|Student|Assessor|Verifier|Examiner|Moderator|Lead(?:er)?)(?:\'s)?\b'
    r')',
    re.IGNORECASE
)

# Date/Time sub-patterns for modular compilation
DATE_SUB_PATTERN = (
    r'(?:'
    r'\d{1,4}[-./]\d{1,2}[-./]\d{1,4}'  # e.g. 2026-06-15, 15/06/2026
    r'|(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*[-.,\s]*\d{0,2}(?:st|nd|rd|th)?[-.,\s]*\d{2,4}?' # e.g. 19th of June 2026
    r')'
)

TIME_SUB_PATTERN = (
    r'(?:'
    r'\b\d{1,2}(?::\d{2})?\s*[APap][Mm]\b'  # e.g. 4pm, 4:00pm, 10am
    r'|\b\d{1,2}:\d{2}\b'                    # e.g. 14:30
    r'|\b\d{4}\s*hrs?\b'                    # e.g. 1600hrs
    r')'
)

TIMEZONE_SUFFIX = r'(?:\s*\(?[A-Za-z\s]+time\)?|\s*\b(?:GMT|BST|EST|EDT|UTC|PST|PDT|CET|CEST|IST|AEST|AEDT)\b)?'

DATETIME_COMP_PATTERN = rf'(?:{DATE_SUB_PATTERN}|{TIME_SUB_PATTERN}){TIMEZONE_SUFFIX}'

COMBINED_DATETIME_PATTERN = (
    rf'{DATETIME_COMP_PATTERN}'
    rf'(?:\s*(?:at|on|by|and|,|/)?\s*{DATETIME_COMP_PATTERN})?'
)

# Match dates and times for submission, presentation, or target feedback
SUBMISSION_FEEDBACK_DATE_PATTERN = re.compile(
    r'(?:'
    r'\b(?:submission|submitted|submit|presentation|present|resit|deadline|deadlines|target\s+feedback|feedback)'
    r'(?:\s*\(.*?\))?'
    r'(?:\s*(?:and|&|or|,|/)?\s*(?:date|time|deadline|target|value|slot|due|dates|times|day|days)){0,3}'
    r'|\b(?:date|time|deadline|target|value|slot|due|dates|times|day|days)'
    r'(?:\s*(?:and|&|or|,|/)?\s*(?:date|time|deadline|target|value|slot|due|dates|times|day|days)){0,2}'
    r'\s+(?:of|for)\s+'
    r'(?:submission|submitted|submit|presentation|present|resit|deadline|deadlines|target\s+feedback|feedback)'
    r'(?:\s*\(.*?\))?'
    r')'
    r'\s*:?'
    r'(?:\s*(?:on|by|at|is|of|for|before|after|no\s+later\s+than|not\s+later\s+than'
    r'|monday|tuesday|wednesday|thursday|friday|saturday|sunday'
    r'|mon|tue|wed|thu|fri|sat|sun'
    r'|[,.\-]'
    r'))*'
    r'\s*'
    + COMBINED_DATETIME_PATTERN,
    re.IGNORECASE
)

# Pattern matching dates and times on their own (for table cell extraction)
DATE_TIME_ONLY_PATTERN = re.compile(
    r'\b' + COMBINED_DATETIME_PATTERN,
    re.IGNORECASE
)

# Keywords indicating a table row contains deadline/submission info
TABLE_ROW_KEYWORD_PATTERN = re.compile(
    r'(?:'
    r'^\s*(?:draft\s+|final\s+|formative\s+|interim\s+|provisional\s+|resit\s+|second\s+|first\s+|main\s+)?'
    r'(?:submission|submitted|submit|presentation|present|resit|deadline|deadlines|target\s+feedback|feedback)'
    r'(?:\s*\(.*?\))?'
    r'(?:\s+(?:and|&|or|/)?\s*(?:date|time|deadline|target|value|slot|due|dates|times|day|days)){0,3}'
    r'\s*:?$'
    r'|\b(?:draft\s+|final\s+|formative\s+|interim\s+|provisional\s+|resit\s+|second\s+|first\s+|main\s+)?'
    r'(?:submission|submitted|submit|presentation|present|resit|deadline|deadlines|target\s+feedback|feedback)'
    r'\s+(?:and|&|or|/)?\s*(?:date|time|deadline|target|value|slot|due|dates|times|day|days)\b'
    r'|\b(?:date|time|deadline|target|value|slot|due|dates|times|day|days)\b'
    r'.*?\b(?:submission|submitted|submit|presentation|present|resit|deadline|deadlines|target\s+feedback|feedback)\b'
    r')',
    re.IGNORECASE
)

# Pattern to match the label part of a submission location field in free-text paragraphs
# e.g. "Submission location: Turnitin", "Submit to: VLE", "Where to submit: Online portal"
SUBMISSION_LOCATION_PATTERN = re.compile(
    r'\b(?:'
    r'submission\s+(?:location|point|portal|platform|link|method|box|folder|area|mode|type|system|channel|url|address|site|page|form)'
    r'|submit(?:ted)?\s+(?:to|via|through|using|on|at|by|with)'
    r'|how\s+to\s+submit'
    r'|where\s+to\s+submit'
    r'|electronic(?:ally)?\s+submit(?:ted)?'
    r'|online\s+submission'
    r'|e-?submission'
    r'|upload\s+(?:location|link|portal|to)'
    r'|submission\s+details'
    # Submission Deadline keywords
    r'|submission\s+deadline'
    r'|submission\s+due'
    r'|deadline'
    # Feedback / Provisional Marks Date keywords
    r'|feedback\s+date'
    r'|return\s+date'
    r'|provisional\s+marks'
    r'|written\s+feedback'
    r')\b.*',
    re.IGNORECASE
)

# Pattern to identify whether a table row's label cell is about submission location
TABLE_ROW_LOCATION_KEYWORD_PATTERN = re.compile(
    r'\b(?:'
    r'submission\s+(?:location|point|portal|platform|link|method|box|folder|area|mode|type|system|channel|url|address|site|page|form)'
    r'|submit(?:ted)?\s+(?:to|via|through|using|on|at|by|with)'
    r'|how\s+to\s+submit'
    r'|where\s+to\s+submit'
    r'|electronic(?:ally)?\s+submit(?:ted)?'
    r'|online\s+submission'
    r'|e-?submission'
    r'|upload\s+(?:location|link|portal|to)'
    r'|submission\s+details'
    # Submission Deadline keywords
    r'|submission\s+deadline'
    r'|submission\s+due'
    r'|deadline'
    # Feedback / Provisional Marks Date keywords
    r'|feedback\s+date'
    r'|return\s+date'
    r'|provisional\s+marks'
    r'|written\s+feedback'
    r')\b',
    re.IGNORECASE
)

SAFE_COLUMN_HEADER_PATTERN = re.compile(
    r'\b(?:Date\s*\(W/C\)|\bDate\b|\bWeek\b|\bSession\b|\bTopic\b|\bTheme\b|\bContent\b)\b',
    re.IGNORECASE
)

# Dynamic domain pattern
DOMAIN_PATTERNS = []
for domain in UNIVERSITY_DOMAINS:
    # Match domain directly or as part of a reference
    escaped = re.escape(domain)
    # Match domain name itself or with variations
    DOMAIN_PATTERNS.append((re.compile(rf'\b[a-zA-Z0-9.-]*{escaped}\b', re.IGNORECASE), " "))
    # Also match the name part before .edu/ac.uk if it's distinctive
    name_part = domain.split('.')[0]
    if name_part.lower() == "ox":
        name_part = "oxford"
    if len(name_part) > 2:
        DOMAIN_PATTERNS.append((re.compile(rf'\b{re.escape(name_part)}\b', re.IGNORECASE), " "))

# Initialize educational keywords and names dynamically
EDUCATIONAL_KEYWORDS = {'university', 'college', 'institute', 'school', 'academy'}
UNIVERSITY_NAME_PATTERNS = []
UNIVERSITY_DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'branding', 'university_db.json')

try:
    with open(UNIVERSITY_DB_FILE, 'r') as f:
        db = json.load(f)
        for univ in db.get('universities', []):
            name = univ.get('name', '')
            if name:
                # Add full name to name patterns list
                UNIVERSITY_NAME_PATTERNS.append((re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE), " "))
                for word in re.findall(r'\b[a-zA-Z]{3,}\b', name):
                    EDUCATIONAL_KEYWORDS.add(word.lower())
            for alias in univ.get('aliases', []):
                if alias:
                    # Add alias to name patterns list
                    UNIVERSITY_NAME_PATTERNS.append((re.compile(rf'\b{re.escape(alias)}\b', re.IGNORECASE), " "))
                    for word in re.findall(r'\b[a-zA-Z]{3,}\b', alias):
                        EDUCATIONAL_KEYWORDS.add(word.lower())
except Exception:
    pass

# Pattern to capture URLs or educational domain references
URL_OR_DOMAIN_PATTERN = re.compile(
    r'\b(?:https?://|www\.)?[a-zA-Z0-9-.]+\.[a-zA-Z]{2,6}(?:/[a-zA-Z0-9-._~:/?#\[\]@!$&\'()*+,;=]*)?\b',
    re.IGNORECASE
)

def is_likely_human_name(text: str, context: str = "") -> bool:
    from redaction.entity_classifier import classify_entity
    classification, action, reasons, score = classify_entity(text, context=context)
    return classification == "PERSON"

def redact_text(text: str) -> str:
    if not text:
        return text

    # Redact Student IDs
    text = STUDENT_ID_PATTERN.sub(lambda m: " ", text)
    
    # Redact Emails
    text = EMAIL_PATTERN.sub(" ", text)
    
    # Redact Phone Numbers
    text = PHONE_PATTERN.sub(" ", text)
    
    # Redact educational URLs and domains ONLY if they belong to the ISSUING_UNIVERSITY
    def replace_url_match(match):
        matched_str = match.group(0)
        from redaction.ownership_manager import get_active_patterns
        for pattern in get_active_patterns():
            if pattern.search(matched_str):
                return " "
        return matched_str
        
    text = URL_OR_DOMAIN_PATTERN.sub(replace_url_match, text)
    
    # Redact Postal Codes
    text = POSTAL_CODE_PATTERN.sub(" ", text)

    # Redact Submission and Target Feedback Dates/Times
    text = SUBMISSION_FEEDBACK_DATE_PATTERN.sub(" ", text)

    # Redact Submission Location fields entirely (label + value)
    text = SUBMISSION_LOCATION_PATTERN.sub(" ", text)

    # Redact only ISSUING_UNIVERSITY names and references
    from redaction.ownership_manager import get_active_patterns
    for pattern in get_active_patterns():
        text = pattern.sub(" ", text)

    # Redact Person Names via Proximity Pattern
    def replace_proximity_name(match):
        full_match = match.group(0)
        name_group = match.group(1)
        if is_likely_human_name(name_group, context=full_match):
            idx = full_match.rfind(name_group)
            if idx != -1:
                return full_match[:idx] + " "
        return full_match
    text = NAME_PROXIMITY_PATTERN.sub(replace_proximity_name, text)
        
    return text

# Pre-load logo perceptual hashes
LOGO_HASHES = {}
if os.path.exists(LOGOS_DIR):
    for filename in os.listdir(LOGOS_DIR):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            logo_path = os.path.join(LOGOS_DIR, filename)
            try:
                with Image.open(logo_path) as img:
                    # Use both phash and dhash for robustness
                    ph = imagehash.phash(img)
                    dh = imagehash.dhash(img)
                    LOGO_HASHES[filename] = (ph, dh)
            except Exception as e:
                print(f"Error loading logo {filename}: {e}")

def is_logo_match(image_bytes: bytes, threshold: int = 12) -> bool:
    """
    Checks if the given image bytes match any of the preloaded logos.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img_ph = imagehash.phash(img)
            img_dh = imagehash.dhash(img)
            
            for logo_name, (ph, dh) in LOGO_HASHES.items():
                ph_diff = img_ph - ph
                dh_diff = img_dh - dh
                # If either hash matches closely, we consider it a match
                if ph_diff <= threshold or dh_diff <= threshold:
                    return True
    except Exception as e:
        # If the image format isn't supported or fails to load, ignore
        pass
    return False

def redact_paragraph_runs(runs, redact_all_dates=False, redact_all_names=False) -> None:
    """
    Smart redaction that handles search patterns split across multiple styled runs (DOCX and PPTX).
    Modifies runs in-place, preserving styling.
    """
    if not runs:
        return
    
    # 1. Reconstruct full text and track run offsets
    full_text = ""
    run_ranges = []  # list of (start_idx, end_idx, run_obj)
    for run in runs:
        run_text = run.text if run.text is not None else ""
        start = len(full_text)
        full_text += run_text
        end = len(full_text)
        run_ranges.append((start, end, run))
            
    # 2. Find all matches
    patterns = [
        (STUDENT_ID_PATTERN, " "),
        (EMAIL_PATTERN, " "),
        (PHONE_PATTERN, " "),
        (POSTAL_CODE_PATTERN, " "),
        (SUBMISSION_FEEDBACK_DATE_PATTERN, " "),
        (SUBMISSION_LOCATION_PATTERN, " "),
    ]
    if redact_all_dates:
        patterns.append((DATE_TIME_ONLY_PATTERN, " "))
    
    all_matches = []
    for pattern, replacement in patterns:
        for m in pattern.finditer(full_text):
            all_matches.append((m.start(), m.end(), m.group(0), replacement))

    # Redact Names via Proximity Pattern
    for m in NAME_PROXIMITY_PATTERN.finditer(full_text):
        name_str = m.group(1)
        if is_likely_human_name(name_str, context=m.group(0)):
            start_idx = m.start(1)
            end_idx = m.end(1)
            all_matches.append((start_idx, end_idx, name_str, " "))

    if redact_all_names:
        for m in NAME_PATTERN.finditer(full_text):
            name_str = m.group(0)
            if is_likely_human_name(name_str, context=full_text):
                all_matches.append((m.start(), m.end(), name_str, " "))
            
    # Redact educational URLs/domains ONLY if they belong to the ISSUING_UNIVERSITY
    for m in URL_OR_DOMAIN_PATTERN.finditer(full_text):
        matched_str = m.group(0)
        from redaction.ownership_manager import get_active_patterns
        belongs_to_issuing = False
        for pattern in get_active_patterns():
            if pattern.search(matched_str):
                belongs_to_issuing = True
                break
        if belongs_to_issuing:
            all_matches.append((m.start(), m.end(), matched_str, " "))
            
    from redaction.ownership_manager import get_active_patterns
    for pattern in get_active_patterns():
        for m in pattern.finditer(full_text):
            all_matches.append((m.start(), m.end(), m.group(0), " "))
            
    if not all_matches:
        return
        
    # Sort and merge overlapping matches
    all_matches.sort(key=lambda x: x[0])
    merged_matches = []
    for current in all_matches:
        if not merged_matches:
            merged_matches.append(current)
        else:
            prev_start, prev_end, prev_text, prev_rep = merged_matches[-1]
            curr_start, curr_end, curr_text, curr_rep = current
            if curr_start < prev_end:
                new_end = max(prev_end, curr_end)
                merged_matches[-1] = (prev_start, new_end, full_text[prev_start:new_end], prev_rep)
            else:
                merged_matches.append(current)
                
    # Process merged matches back-to-front (descending by start index)
    merged_matches.sort(key=lambda x: x[0], reverse=True)
    
    for start, end, match_text, replacement in merged_matches:
        # Find overlapping runs
        overlapping = []
        for r_start, r_end, run in run_ranges:
            if max(r_start, start) < min(r_end, end):
                overlapping.append((r_start, r_end, run))
                
        if not overlapping:
            continue
            
        # Replace overlap in-place
        for i, (r_start, r_end, run) in enumerate(overlapping):
            run_text = run.text if run.text is not None else ""
            prefix = ""
            suffix = ""
            
            if r_start < start:
                prefix = run_text[:start - r_start]
            if r_end > end:
                suffix = run_text[end - r_start:]
                
            if i == 0:
                run.text = prefix + replacement + suffix
            else:
                run.text = prefix + suffix

def redact_paragraph_runs_with_pattern(runs, pattern, replacement="[REMOVED]") -> None:
    """
    Apply a specific regex pattern to a group of runs as a unified string,
    mapping offsets back to individual runs to redact in-place.
    """
    if not runs:
        return
    
    # 1. Reconstruct full text and track run offsets
    full_text = ""
    run_ranges = []
    for run in runs:
        run_text = run.text if run.text is not None else ""
        start = len(full_text)
        full_text += run_text
        end = len(full_text)
        run_ranges.append((start, end, run))
            
    # 2. Find matches
    all_matches = []
    for m in pattern.finditer(full_text):
        all_matches.append((m.start(), m.end(), m.group(0), replacement))
            
    if not all_matches:
        return
        
    # Process matches back-to-front
    all_matches.sort(key=lambda x: x[0], reverse=True)
    
    for start, end, match_text, rep in all_matches:
        # Find overlapping runs
        overlapping = []
        for r_start, r_end, run in run_ranges:
            if max(r_start, start) < min(r_end, end):
                overlapping.append((r_start, r_end, run))
                
        if not overlapping:
            continue
            
        # Replace overlap in-place
        for i, (r_start, r_end, run) in enumerate(overlapping):
            run_text = run.text if run.text is not None else ""
            prefix = ""
            suffix = ""
            
            if r_start < start:
                prefix = run_text[:start - r_start]
            if r_end > end:
                suffix = run_text[end - r_start:]
                
            if i == 0:
                run.text = prefix + rep + suffix
            else:
                run.text = prefix + suffix


