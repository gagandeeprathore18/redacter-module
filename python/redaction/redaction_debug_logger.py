"""
Redaction Debug Logger
======================
Logs every committed redaction decision to logs/redaction_debug.json.

Each entry contains:
  candidate       – the text being redacted
  classification  – entity classification (PERSON, EMAIL, etc.)
  page            – 1-indexed page number (None for DOCX/PPTX)
  bbox            – [x0, y0, x1, y1] bounding box in document points (None for DOCX/PPTX)
  bbox_width      – width of the bounding box in points (None if no bbox)
  bbox_height     – height of the bounding box in points (None if no bbox)
  ocr_block_text  – surrounding context/paragraph text at time of redaction
  source          – which processor wrote this entry (pdf / docx / pptx)
  document        – filename being processed
"""

import json
import os
import threading

_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs"
)
DEBUG_LOG_FILE = os.path.join(_LOGS_DIR, "redaction_debug.json")

_lock = threading.Lock()

# Per-document state (set by processor before processing starts)
_current_document: str = ""
_current_source: str = ""


def set_document_context(document: str, source: str) -> None:
    """Call at the start of each document processing to set context."""
    global _current_document, _current_source
    _current_document = document
    _current_source = source


def log_redaction(
    candidate: str,
    classification: str,
    page: int | None = None,
    bbox: list | None = None,
    ocr_block_text: str = "",
    document: str | None = None,
    source: str | None = None,
) -> None:
    """
    Append a single redaction entry to the debug log file.

    Parameters
    ----------
    candidate        : The string that was redacted.
    classification   : Entity category (e.g. 'PERSON', 'EMAIL').
    page             : 1-indexed page number. None for non-paginated formats.
    bbox             : [x0, y0, x1, y1] in document points. None if unavailable.
    ocr_block_text   : Surrounding paragraph / block text for context.
    document         : Filename being processed (defaults to module-level state).
    source           : Processor type: 'pdf', 'docx', 'pptx' (defaults to module-level state).
    """
    if not candidate or not candidate.strip():
        return

    bbox_width = None
    bbox_height = None
    if bbox and len(bbox) == 4:
        bbox_width = round(bbox[2] - bbox[0], 2)
        bbox_height = round(bbox[3] - bbox[1], 2)

    entry = {
        "candidate": candidate.strip(),
        "classification": classification,
        "page": page,
        "bbox": [round(v, 2) for v in bbox] if bbox else None,
        "bbox_width": bbox_width,
        "bbox_height": bbox_height,
        "ocr_block_text": ocr_block_text.strip() if ocr_block_text else "",
        "source": source or _current_source,
        "document": document or _current_document,
    }

    os.makedirs(_LOGS_DIR, exist_ok=True)

    with _lock:
        # Read existing entries
        existing = []
        if os.path.exists(DEBUG_LOG_FILE):
            try:
                with open(DEBUG_LOG_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
            except Exception:
                existing = []

        existing.append(entry)

        try:
            with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[redaction_debug_logger] Failed to write log: {e}")


def clear_debug_log() -> None:
    """Wipe the debug log file. Call at the start of a fresh processing run if desired."""
    os.makedirs(_LOGS_DIR, exist_ok=True)
    with _lock:
        try:
            with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
        except Exception as e:
            print(f"[redaction_debug_logger] Failed to clear log: {e}")


def get_debug_log() -> list:
    """Return current debug log entries as a list."""
    if not os.path.exists(DEBUG_LOG_FILE):
        return []
    try:
        with open(DEBUG_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
