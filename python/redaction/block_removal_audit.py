import json
import os

AUDIT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'block_removal_audit.json'
)

def log_block_removal(anchor: str, start_paragraph: int, end_paragraph: int, boundary_detected: bool, protected_sections_encountered: list, decision: str, block_id: str = None, paragraphs_removed: int = 0):
    entry = {
        "anchor": anchor,
        "start_paragraph": start_paragraph,
        "end_paragraph": end_paragraph,
        "boundary_detected": boundary_detected,
        "protected_sections_encountered": protected_sections_encountered,
        "decision": decision
    }
    if block_id is not None:
        entry["block_id"] = block_id
    if paragraphs_removed > 0:
        entry["paragraphs_removed"] = paragraphs_removed

    try:
        logs = []
        if os.path.exists(AUDIT_FILE):
            with open(AUDIT_FILE, 'r') as f:
                try:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
                except Exception:
                    logs = []
        logs.append(entry)
        with open(AUDIT_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Error writing to block removal audit log: {e}")
