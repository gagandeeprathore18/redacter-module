import json
import os

AUDIT_LOG_FILE = "/home/user/drafter-module/redaction_audit.json"

_logs = []

def clear_logs():
    global _logs
    _logs = []

def log_detection(target: str, detected: bool, block_found: bool, reason: str = None):
    entry = {
        "target": target,
        "detected": detected,
        "block_found": block_found,
        "reason": reason
    }
    _logs.append(entry)
    save_logs()

def log_candidate(candidate: str, classification: str, action: str, score: float = 0, reasons: list = None):
    entry = {
        "candidate": candidate,
        "classification": classification,
        "action": action,
        "score": score,
        "reasons": reasons or []
    }
    _logs.append(entry)
    save_logs()

def save_logs():
    try:
        with open(AUDIT_LOG_FILE, "w") as f:
            json.dump(_logs, f, indent=2)
    except Exception as e:
        print(f"Error saving audit log: {e}")

def get_logs():
    return _logs
