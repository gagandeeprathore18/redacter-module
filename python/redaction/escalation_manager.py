import re
import os
import json
from llm.gpt_client import call_gpt_verification, load_config

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs"
)


# Cache of all candidate details encountered in the current document scan pass
# Key: (text, context)
# Value: dict containing classification result from GPT, or None
_gpt_cache = {}

# List of accumulated candidate objects to escalate
_escalated_candidates = []
_candidate_counter = 0
_total_candidates_processed = 0

_document_id = "UNKNOWN"
_audit_records = {}
_filter_report = {
    "total_extracted": 0,
    "filtered_out": 0,
    "remaining_candidates": 0,
    "rejection_breakdown": {
        "PARAGRAPH_CONTENT": 0,
        "LONG_TEXT": 0,
        "MULTI_SENTENCE": 0,
        "STRUCTURAL_CONTENT": 0,
        "INSTRUCTIONAL_CONTENT": 0,
        "FRAGMENT_CONTENT": 0,
        "HEADING_CONTENT": 0,
    },
    "rejected_candidates": []
}
# Phase 5 — per-document candidate rejection counters
_heading_filter_counts = {
    "HEADING_CONTENT": 0,
    "STRUCTURAL_CONTENT": 0,
    "RUBRIC_CONTENT": 0,
    "READING_LIST_CONTENT": 0,
}

_paragraph_candidates_removed = 0
_grading_band_matches = 0
_rubric_matches = 0
_rubric_sections_preserved = 0

def clear_cache():
    global _escalated_candidates, _candidate_counter, _gpt_cache, _total_candidates_processed
    global _document_id, _audit_records, _escalation_breakdown, _filter_report
    global _paragraph_candidates_removed, _grading_band_matches, _rubric_matches, _rubric_sections_preserved
    _gpt_cache = {}
    _escalated_candidates = []
    _candidate_counter = 0
    _total_candidates_processed = 0
    _document_id = "UNKNOWN"
    _audit_records = {}
    _paragraph_candidates_removed = 0
    _grading_band_matches = 0
    _rubric_matches = 0
    _rubric_sections_preserved = 0
    _escalation_breakdown = {
        "LOW_CONFIDENCE": 0,
        "CLASSIFIER_CONFLICT": 0,
        "UNKNOWN_PATTERN": 0,
        "HIGH_IMPACT_ACTION": 0,
        "UNIVERSITY_BRANDING_VERIFICATION": 0,
        "DATE_CANDIDATE_ESCALATION": 0
    }
    _filter_report = {
        "total_extracted": 0,
        "filtered_out": 0,
        "remaining_candidates": 0,
        "rejection_breakdown": {
            "PARAGRAPH_CONTENT": 0,
            "LONG_TEXT": 0,
            "MULTI_SENTENCE": 0,
            "STRUCTURAL_CONTENT": 0,
            "INSTRUCTIONAL_CONTENT": 0,
            "FRAGMENT_CONTENT": 0,
            "HEADING_CONTENT": 0,
        },
        "rejected_candidates": []
    }
    global _heading_filter_counts
    _heading_filter_counts = {
        "HEADING_CONTENT": 0,
        "STRUCTURAL_CONTENT": 0,
        "RUBRIC_CONTENT": 0,
        "READING_LIST_CONTENT": 0,
    }
    try:
        from redaction.ownership_manager import clear_detected_universities
        clear_detected_universities()
    except Exception:
        pass
    try:
        from redaction.entity_classifier import reload_learned_classifications
        reload_learned_classifications()
    except Exception:
        pass
    try:
        from redaction.redaction_audit import RedactionAudit
        RedactionAudit.clear()
    except Exception:
        pass


def is_capitalized_phrase(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    words = stripped.split()
    if not words:
        return False
    capitalized_count = sum(1 for w in words if w and w[0].isupper())
    return capitalized_count >= 1 and (len(words) == capitalized_count or len(words) <= 4)

def get_escalation_reasons(text: str, context: str, classification: str, action: str, score: float, reasons: list) -> list:
    if classification in ("ACADEMIC_CONTENT", "SECTION_HEADING", "PROTECTED_SECTION", "ACADEMIC_TITLE") and action not in ("REDACT", "REMOVE_BLOCK"):
        return []

    # Check for classifier conflict to set score above threshold and avoid LOW_CONFIDENCE shadowing
    has_exclusion_reasons = any("exclusion" in r or "heading" in r or "numbered" in r for r in reasons)
    conflict_trigger = False
    if has_exclusion_reasons and classification in ("PERSON", "UNIVERSITY_ENTITY"):
        conflict_trigger = True
    elif classification in ("PERSON", "UNIVERSITY_ENTITY", "UNKNOWN"):
        try:
            from redaction.academic_title_detector import detect_academic_title
            from redaction.human_name_classifier import score_human_name
            is_academic_title, _ = detect_academic_title(text)
            if is_academic_title and score_human_name(text, context) > 0:
                conflict_trigger = True
        except Exception:
            pass

    if conflict_trigger:
        score = max(score, 90.0)

    config = load_config()
    threshold = config.get("escalation_confidence_threshold", config.get("confidence_threshold", 50.0))
    esc_reasons = []

    # DATE_CANDIDATE always triggers GPT escalation
    if classification == "DATE_CANDIDATE":
        esc_reasons.append("DATE_CANDIDATE_ESCALATION")

    # 1. LOW_CONFIDENCE
    if 0 < score < threshold and classification in ("PERSON", "UNIVERSITY_ENTITY", "BUSINESS_FIELD", "METADATA_FIELD"):
        esc_reasons.append("LOW_CONFIDENCE")

    # 2. CLASSIFIER_CONFLICT
    if conflict_trigger:
        esc_reasons.append("CLASSIFIER_CONFLICT")

    # 3. UNKNOWN_PATTERN
    if (classification == "UNKNOWN" or (score <= 0 and classification not in ("ACADEMIC_TITLE", "SECTION_HEADING", "PROTECTED_SECTION", "ACADEMIC_CONTENT"))) and is_capitalized_phrase(text):
        esc_reasons.append("UNKNOWN_PATTERN")

    # 4. HIGH_IMPACT_ACTION
    if action in ("REDACT", "REMOVE_BLOCK") and score < 100:
        norm_text = text.lower().strip()
        protected_keywords = ["confidentiality", "integrity", "learning", "reading", "reference", "criteria", "outcomes"]
        if any(kw in norm_text for kw in protected_keywords):
            esc_reasons.append("HIGH_IMPACT_ACTION")

    # 5. UNIVERSITY_BRANDING_VERIFICATION
    try:
        from redaction.ownership_manager import get_issuing_university, get_detected_universities
        issuing = get_issuing_university()
        if classification == "UNIVERSITY_ENTITY":
            distinct_unis = get_detected_universities()
            multiple_unis = len(distinct_unis) > 1
            
            is_match = False
            if issuing:
                from redaction.normalizer import normalize_text
                from redaction.fuzzy_matcher import is_fuzzy_match
                norm_text = normalize_text(text)
                norm_issuing = normalize_text(issuing)
                
                from redaction.ownership_manager import get_issuing_aliases
                aliases = get_issuing_aliases() or []
                
                if norm_text == norm_issuing or is_fuzzy_match(norm_text, norm_issuing, threshold=80.0, partial=True):
                    is_match = True
                else:
                    for alias in aliases:
                        norm_alias = normalize_text(alias)
                        if norm_text == norm_alias or is_fuzzy_match(norm_text, norm_alias, threshold=80.0, partial=True):
                            is_match = True
                            break
            
            # Escalate if:
            # 1. No issuing university identified from logo (confidence low / missing)
            # 2. Or multiple universities appear in the document
            # 3. Or the candidate does not match the identified issuing university
            if not issuing or multiple_unis or not is_match:
                esc_reasons.append("UNIVERSITY_BRANDING_VERIFICATION")
    except Exception:
        pass

    return esc_reasons

def check_escalation_criteria(text: str, context: str, classification: str, action: str, score: float, reasons: list) -> bool:
    """
    Evaluates whether a Stage 1 candidate needs to be escalated to Stage 2 (GPT).
    """
    return len(get_escalation_reasons(text, context, classification, action, score, reasons)) > 0

# ---------------------------------------------------------------------------
# Phase 4 – Heading Filter Report writer  (logs/heading_filter_report.json)
# Phase 6 – Auto-promote repeated headings to learned_headings.json
# ---------------------------------------------------------------------------

_HEADING_REPORT_FILE = os.path.join(LOGS_DIR, "heading_filter_report.json")
_heading_seen_counts: dict = {}   # track repeat count per heading text

def _write_heading_filter_entry(candidate: str, reason: str, category: str) -> None:
    """Append one entry to heading_filter_report.json."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    entry = {"candidate": candidate, "action": "SKIPPED", "reason": reason, "category": category}
    try:
        existing = []
        if os.path.exists(_HEADING_REPORT_FILE):
            with open(_HEADING_REPORT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
        existing.append(entry)
        with open(_HEADING_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[heading_filter] Failed to write report: {e}")

def _promote_if_repeated(text: str, threshold: int = 3) -> None:
    """
    Phase 6 – If a heading text appears >= threshold times across documents,
    promote it to learned_headings.json so it is caught instantly next time.
    """
    key = text.strip().lower()
    _heading_seen_counts[key] = _heading_seen_counts.get(key, 0) + 1
    if _heading_seen_counts[key] >= threshold:
        try:
            from redaction.heading_detector import promote_to_learned
            promote_to_learned(text)
        except Exception:
            pass


def register_candidate_scan(text: str, context: str, classification: str, action: str, score: float, reasons: list):
    """
    Registers a candidate during Stage 1 scan pass. If it requires escalation,
    accumulates it for the batch GPT request.
    """
    global _candidate_counter, _total_candidates_processed, _filter_report, _heading_filter_counts
    global _paragraph_candidates_removed, _grading_band_matches, _rubric_matches, _rubric_sections_preserved
    
    pregate_reasons = {
        "paragraph_detector_pregate",
        "grading_band_detector_pregate",
        "rubric_detector_pregate",
        "academic_allowlist_pregate",
        "assessment_type_pregate",
        "lms_platform_pregate"
    }
    if reasons and any(r in pregate_reasons for r in reasons):
        if "paragraph_detector_pregate" in reasons:
            _paragraph_candidates_removed += 1
            _filter_report["total_extracted"] += 1
            _filter_report["filtered_out"] += 1
            _filter_report["rejection_breakdown"]["PARAGRAPH_CONTENT"] = (
                _filter_report["rejection_breakdown"].get("PARAGRAPH_CONTENT", 0) + 1
            )
            _filter_report["rejected_candidates"].append({
                "candidate": text,
                "reason": "PARAGRAPH_CONTENT",
                "word_count": len(text.split())
            })
        elif "grading_band_detector_pregate" in reasons:
            _grading_band_matches += 1
        elif "rubric_detector_pregate" in reasons:
            _rubric_matches += 1
            _rubric_sections_preserved += 1
            _heading_filter_counts["RUBRIC_CONTENT"] = _heading_filter_counts.get("RUBRIC_CONTENT", 0) + 1
        return

    _total_candidates_processed += 1
    
    key = (text, context)
    if key in _gpt_cache:
        return

    # Phase 2: Log every extracted candidate
    try:
        from redaction.redaction_audit import RedactionAudit
        RedactionAudit.log({
            "candidate": text,
            "page": None,
            "stage": "EXTRACTED",
            "candidate_length": len(text),
            "word_count": len(text.split()),
            "source_detector": classification + "_PATTERN" if classification else "UNKNOWN"
        })
    except Exception:
        pass

    # ------------------------------------------------------------------ #
    # Phase 3 – Hard Heading / Structural Content Rejection Gate           #
    # Runs BEFORE quality validator and classification.                    #
    # Headings NEVER reach GPT or the redaction engine.                   #
    # ------------------------------------------------------------------ #
    try:
        from redaction.heading_detector import HeadingDetector
        from redaction.structural_content_detector import StructuralContentDetector

        _heading_category = HeadingDetector.get_category(text)
        _structural_category = StructuralContentDetector.get_category(text)

        _reject_reason = None
        if _heading_category is not None:
            _reject_reason = "HEADING_CONTENT"
        elif _structural_category is not None:
            _reject_reason = "STRUCTURAL_CONTENT"

        if _reject_reason:
            _filter_report["total_extracted"] += 1
            _filter_report["filtered_out"] += 1
            _filter_report["rejection_breakdown"][_reject_reason] = (
                _filter_report["rejection_breakdown"].get(_reject_reason, 0) + 1
            )
            _filter_report["rejected_candidates"].append({
                "candidate": text,
                "reason": _reject_reason,
                "category": _heading_category or _structural_category,
                "word_count": len(text.split())
            })
            # Phase 5 counters
            _heading_filter_counts[_reject_reason] = _heading_filter_counts.get(_reject_reason, 0) + 1

            # Log Heading/Structural Filter Decisions
            try:
                from redaction.redaction_audit import RedactionAudit
                RedactionAudit.log({
                    "candidate": text,
                    "stage": "HEADING_FILTER" if _reject_reason == "HEADING_CONTENT" else "STRUCTURAL_FILTER",
                    "decision": "REJECTED",
                    "reason": _heading_category or _structural_category or _reject_reason
                })
            except Exception:
                pass

            # Phase 4 – Write to heading_filter_report.json
            try:
                _write_heading_filter_entry(text, _reject_reason, _heading_category or _structural_category)
            except Exception:
                pass

            # Phase 6 – Auto-promote repeated headings into learned_headings.json
            try:
                _promote_if_repeated(text)
            except Exception:
                pass

            return  # Hard stop — do NOT classify, escalate, or redact
    except Exception:
        pass  # Never block processing due to detector errors

    # Candidate Quality Filter Layer (Phase 1 & 7)
    from redaction.quality_validator import CandidateQualityValidator
    _filter_report["total_extracted"] += 1
    val_res = CandidateQualityValidator.validate(text, classification, score, reasons)
    if not val_res["eligible_for_escalation"]:
        reason = val_res["reason"]
        _filter_report["filtered_out"] += 1
        if reason in _filter_report["rejection_breakdown"]:
            _filter_report["rejection_breakdown"][reason] += 1
        else:
            _filter_report["rejection_breakdown"][reason] = 1
        _filter_report["rejected_candidates"].append({
            "candidate": text,
            "reason": reason,
            "word_count": val_res["word_count"]
        })

        # Log Quality Filter Reject
        try:
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "QUALITY_FILTER",
                "decision": "REJECTED",
                "reason": reason
            })
        except Exception:
            pass

        return

    _filter_report["remaining_candidates"] += 1

    # Phase 6: Register detected university BEFORE evaluating escalation reasons
    if classification == "UNIVERSITY_ENTITY":
        try:
            from redaction.ownership_manager import register_detected_university
            register_detected_university(text)
        except Exception:
            pass

    # Check for classifier conflict to set score above threshold and avoid LOW_CONFIDENCE shadowing
    has_exclusion_reasons = any("exclusion" in r or "heading" in r or "numbered" in r for r in reasons)
    conflict_trigger = False
    if has_exclusion_reasons and classification in ("PERSON", "UNIVERSITY_ENTITY"):
        conflict_trigger = True
    elif classification in ("PERSON", "UNIVERSITY_ENTITY", "UNKNOWN"):
        try:
            from redaction.academic_title_detector import detect_academic_title
            from redaction.human_name_classifier import score_human_name
            is_academic_title, _ = detect_academic_title(text)
            if is_academic_title and score_human_name(text, context) > 0:
                conflict_trigger = True
        except Exception:
            pass

    if conflict_trigger:
        score = max(score, 90.0)

    esc_reasons = get_escalation_reasons(text, context, classification, action, score, reasons)
    if esc_reasons:
        # Phase 5 Log: Escalation Decisions
        try:
            from redaction.redaction_audit import RedactionAudit
            RedactionAudit.log({
                "candidate": text,
                "stage": "ESCALATION_CHECK",
                "decision": "ESCALATE",
                "classification": classification,
                "reason": esc_reasons[0]
            })
        except Exception:
            pass

        _candidate_counter += 1
        _escalated_candidates.append({
            "id": _candidate_counter,
            "candidate": text,
            "context": context,
            "python_prediction": classification,
            "python_confidence": int(score) if score > 0 else 0,
            "key": key
        })
        # Placeholder in cache
        _gpt_cache[key] = None
        
        # Increment breakdown counts
        for r in esc_reasons:
            if r in _escalation_breakdown:
                _escalation_breakdown[r] += 1
                
        # Phase 2 Attributions
        primary_reason = esc_reasons[0]
        classifier_1 = None
        classifier_2 = None
        if "CLASSIFIER_CONFLICT" in esc_reasons:
            has_exclusion_reasons = any("exclusion" in r or "heading" in r or "numbered" in r for r in reasons)
            if has_exclusion_reasons and classification in ("PERSON", "UNIVERSITY_ENTITY"):
                classifier_1 = classification
                if any("exclusion" in r for r in reasons):
                    classifier_2 = "ACADEMIC_EXCLUSION"
                elif any("heading" in r for r in reasons):
                    classifier_2 = "SECTION_HEADING"
                elif any("numbered" in r for r in reasons):
                    classifier_2 = "NUMBERED_SECTION"
                else:
                    classifier_2 = "UNKNOWN"
            else:
                try:
                    from redaction.academic_title_detector import detect_academic_title
                    from redaction.human_name_classifier import score_human_name
                    is_academic_title, _ = detect_academic_title(text)
                    if is_academic_title and score_human_name(text, context) > 0:
                        classifier_1 = "PERSON"
                        classifier_2 = "ACADEMIC_TITLE"
                except Exception:
                    pass

        # Record initial audit details
        _audit_records[key] = {
            "document_id": _document_id,
            "candidate": text,
            "context": context,
            "python_prediction": classification,
            "python_confidence": int(score) if score > 0 else 0,
            "escalation_reasons": esc_reasons,
            "escalation_reason": primary_reason,
            "classifier_1": classifier_1,
            "classifier_2": classifier_2,
            "gpt_prediction": None,
            "gpt_confidence": None,
            "request_cost_usd": 0.0,
            "response_time_ms": 0,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "final_classification": classification,
            "action": "PRESERVE" if action == "KEEP" else "REDACT"
        }

def write_escalation_audit_log(doc_id: str):
    try:
        log_dir = os.path.join(LOGS_DIR, "escalations")
        os.makedirs(log_dir, exist_ok=True)
        
        doc_log_path = os.path.join(log_dir, f"{doc_id}.json")
        cand_list = list(_audit_records.values())
        escalated_count = len(cand_list)
        
        # Phase 8: Escalation Cap & Monitoring
        warnings = []
        if escalated_count > 30:
            warnings.append({
                "severity": "HIGH",
                "message": "Escalation limit exceeded."
            })
        if escalated_count > 75:
            warnings.append({
                "severity": "CRITICAL",
                "message": "GPT is acting as a primary classifier instead of a fallback classifier."
            })
        elif escalated_count > 50:
            warnings.append({
                "severity": "HIGH",
                "message": "Escalation volume exceeds optimization target."
            })
            
        doc_data = {
            "document_id": doc_id,
            "total_candidates": _total_candidates_processed,
            "escalated_candidates": escalated_count,
            "escalation_breakdown": _escalation_breakdown,
            "top_escalation_reasons": _escalation_breakdown,
            "warnings": warnings,
            "candidates": cand_list
        }
        
        with open(doc_log_path, "w") as f:
            json.dump(doc_data, f, indent=2)

        # Phase 8: Candidate Rejection Logging
        try:
            filter_report_file = os.path.join(LOGS_DIR, "candidate_filter_report.json")
            filter_data = {}
            if os.path.exists(filter_report_file):
                try:
                    with open(filter_report_file, "r") as f:
                        filter_data = json.load(f)
                except Exception:
                    pass
            filter_data[doc_id] = _filter_report
            with open(filter_report_file, "w") as f:
                json.dump(filter_data, f, indent=2)
        except Exception as fe:
            print(f"Warning: Failed to write candidate filter report: {fe}")
            
        # Update global analytics store
        analytics_file = os.path.join(LOGS_DIR, "escalation_analytics.json")
        analytics_data = {}
        
        if os.path.exists(analytics_file):
            try:
                with open(analytics_file, "r") as f:
                    analytics_data = json.load(f)
            except Exception:
                pass
                
        # 1. Update Escalation Frequencies
        freqs = analytics_data.setdefault("escalation_frequencies", {})
        for audit in cand_list:
            cand_text = audit["candidate"]
            freqs[cand_text] = freqs.get(cand_text, 0) + 1
        
        # 2. Update Python vs GPT Disagreements
        disagreements = analytics_data.setdefault("python_gpt_disagreements", {})
        for audit in cand_list:
            py_pred = audit["python_prediction"]
            gpt_pred = audit["gpt_prediction"]
            if gpt_pred and py_pred != gpt_pred:
                key = f"{py_pred} → {gpt_pred}"
                disagreements[key] = disagreements.get(key, 0) + 1

        # 3. Phase 10: Token Telemetry
        total_prompt_tokens = sum(c.get("token_usage", {}).get("prompt_tokens", 0) for c in cand_list)
        total_completion_tokens = sum(c.get("token_usage", {}).get("completion_tokens", 0) for c in cand_list)
        total_cost = sum(c.get("request_cost_usd", 0.0) for c in cand_list)
        
        token_telemetry = analytics_data.setdefault("token_telemetry", {})
        token_telemetry[doc_id] = {
            "document": doc_id,
            "input_tokens": total_prompt_tokens,
            "output_tokens": total_completion_tokens,
            "cost": round(total_cost, 6),
            "escalated_candidates": escalated_count,
            "filtered_candidates": _filter_report.get("filtered_out", 0)
        }
        
        # 4. Phase 11: Escalation Source Analysis
        source_analysis = analytics_data.setdefault("escalation_source_analysis", {
            "LOW_CONFIDENCE": 0,
            "CLASSIFIER_CONFLICT": 0,
            "UNKNOWN_PATTERN": 0,
            "HIGH_IMPACT_ACTION": 0,
            "UNIVERSITY_BRANDING_VERIFICATION": 0
        })
        for reason, count in _escalation_breakdown.items():
            source_analysis[reason] = source_analysis.get(reason, 0) + count
            
        with open(analytics_file, "w") as f:
            json.dump(analytics_data, f, indent=2)
            
        # Unified rich telemetry logging (Phase 1 & 10)
        try:
            from llm.gpt_client import load_config
            from datetime import datetime as dt
            config = load_config()
            log_path = config.get("telemetry_log_path")
            if log_path:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                
                total_prompt_tokens = sum(c.get("token_usage", {}).get("prompt_tokens", 0) for c in cand_list)
                total_completion_tokens = sum(c.get("token_usage", {}).get("completion_tokens", 0) for c in cand_list)
                total_cost = sum(c.get("request_cost_usd", 0.0) for c in cand_list)
                total_latency = sum(c.get("response_time_ms", 0) for c in cand_list)
                
                telemetry_entry = {
                    "timestamp": dt.utcnow().isoformat() + "Z",
                    "document_id": doc_id,
                    "total_candidates": _total_candidates_processed,
                    "escalated_candidates": escalated_count,
                    "top_escalation_reasons": _escalation_breakdown,
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "total_tokens": total_prompt_tokens + total_completion_tokens,
                    "request_cost_usd": round(total_cost, 6),
                    "response_time_ms": total_latency,
                    "model": config.get("model", "gpt-4o-mini"),
                    "warnings": warnings,
                    # Phase 8: Telemetry counters
                    "heading_candidates_removed": _heading_filter_counts.get("HEADING_CONTENT", 0),
                    "structural_candidates_removed": _heading_filter_counts.get("STRUCTURAL_CONTENT", 0),
                    "paragraph_candidates_removed": _paragraph_candidates_removed,
                    "grading_band_matches": _grading_band_matches,
                    "rubric_matches": _rubric_matches,
                    "rubric_sections_preserved": _rubric_sections_preserved,
                }
                
                with open(log_path, 'a') as f:
                    f.write(json.dumps(telemetry_entry) + "\n")
        except Exception as te:
            print(f"Warning: Failed to log diagnostics to telemetry.log: {te}")
            
    except Exception:
        pass

def print_console_debug():
    print("=====================================")
    print("GPT ESCALATION AUDIT")
    print("====================")
    for key, audit in _audit_records.items():
        reasons = audit.get("escalation_reasons", [])
        reason_str = ", ".join(reasons)
        print(f"\n[{reason_str}]")
        print(f"Candidate:\n{audit['candidate']}")
        print(f"Python:\n{audit['python_prediction']} ({audit['python_confidence']}%)")
        print("\n---")
    print("=====================================")

def run_gpt_review(issuing_university: str, doc_id: str = "UNKNOWN"):
    """
    Executes the batch GPT query for all accumulated escalated candidates
    and stores the classifications in the cache.
    """
    global _escalated_candidates, _document_id
    _document_id = doc_id
    
    if not _escalated_candidates:
        write_escalation_audit_log(doc_id)
        return

    for key in _audit_records:
        _audit_records[key]["document_id"] = doc_id

    res_tuple = call_gpt_verification(_escalated_candidates, issuing_university, doc_id)
    if isinstance(res_tuple, tuple):
        gpt_results, telemetry = res_tuple
    else:
        gpt_results = res_tuple
        telemetry = None

    N = len(_escalated_candidates)
    
    # Map results back to the cache
    for cand in _escalated_candidates:
        key = cand["key"]
        cand_id = cand["id"]
        
        gpt_pred = None
        gpt_conf = None
        cost_share = 0.0
        time_share = 0
        prompt_tokens_share = 0
        completion_tokens_share = 0
        
        if cand_id in gpt_results:
            res = gpt_results[cand_id]
            _gpt_cache[key] = res
            gpt_pred = res.get("classification")
            gpt_conf = res.get("confidence", 100)
        else:
            _gpt_cache[key] = None # Fallback to python prediction
            
        if telemetry:
            prompt_tokens_share = int(telemetry.get("prompt_tokens", 0) / N)
            completion_tokens_share = int(telemetry.get("completion_tokens", 0) / N)
            cost_share = float(telemetry.get("cost", 0.0) / N)
            time_share = int(telemetry.get("duration_ms", 0) / N)
            
        if key in _audit_records:
            audit = _audit_records[key]
            audit["gpt_prediction"] = gpt_pred
            audit["gpt_confidence"] = gpt_conf
            audit["request_cost_usd"] = round(cost_share, 6)
            audit["response_time_ms"] = time_share
            audit["token_usage"] = {
                "prompt_tokens": prompt_tokens_share,
                "completion_tokens": completion_tokens_share,
                "total_tokens": prompt_tokens_share + completion_tokens_share
            }
            
            final_class = gpt_pred if gpt_pred else audit["python_prediction"]

            # ---------------------------------------------------------------------------
            # GPT AUTHORITATIVE ACTION MAPPING
            # GPT's classification is the final word. No Python re-evaluation,
            # no sensitivity score checks, no validate_redaction overrides.
            # The action is derived purely from the canonical classification map.
            # ---------------------------------------------------------------------------
            action = res.get("action") if (cand_id in gpt_results and res) else None
            if action not in ("REDACT", "PRESERVE"):
                _REDACT_CLASSES = {
                    "PERSON", "UNIVERSITY_BRANDING", "UNIVERSITY_ENTITY",
                    "METADATA_FIELD", "BUSINESS_FIELD", "DATE_TIME_VALUE",
                    "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE"
                }
                action = "REDACT" if final_class in _REDACT_CLASSES else "PRESERVE"

            audit["final_classification"] = final_class
            audit["action"] = action
            audit["gpt_authoritative"] = gpt_pred is not None

    # Update learned classifications json file
    if isinstance(gpt_results, dict) and gpt_results:
        try:
            from redaction.normalizer import normalize_text
            learned_file_path = os.path.join(LOGS_DIR, "learned_classifications.json")
            existing_rules = {}
            if os.path.exists(learned_file_path):
                try:
                    with open(learned_file_path, "r") as f:
                        existing_rules = json.load(f)
                except Exception:
                    existing_rules = {}
            
            updated = False
            for cand_id, res in gpt_results.items():
                for cand in _escalated_candidates:
                    if cand["id"] == cand_id:
                        text_to_save = cand["candidate"]
                        norm_text = normalize_text(text_to_save)
                        classification_to_save = res.get("classification")
                        if classification_to_save:
                            existing_rules[norm_text] = classification_to_save
                            updated = True
                        break
            
            if updated:
                os.makedirs(os.path.dirname(learned_file_path), exist_ok=True)
                with open(learned_file_path, "w") as f:
                    json.dump(existing_rules, f, indent=2)
                # Reload immediately in memory
                from redaction.entity_classifier import reload_learned_classifications
                reload_learned_classifications()
        except Exception as e:
            print(f"Error updating learned classifications: {e}")

    # Phase 9, 10, 11: Generate reports
    try:
        from redaction.redaction_audit import RedactionAudit
        # Ground truth expectations for testing the single instance
        expected_decisions = {
            "Research Methods": "PRESERVE",
            "Claire Ngo": "REDACT",
            "Nargisa Simansone": "REDACT",
            "Sarah Johnson": "REDACT"
        }
        RedactionAudit.generate_accuracy_review(expected_decisions)
        
        # Write summary report
        summary = RedactionAudit.generate_summary(doc_id)
        summary_file = os.path.join(LOGS_DIR, "audit_summary.json")
        with open(summary_file, "w", encoding="utf-8") as sf:
            json.dump(summary, sf, indent=2)
    except Exception as re_err:
        print(f"Error generating redaction audit reports: {re_err}")

    write_escalation_audit_log(doc_id)
    
    if os.environ.get("DEVELOPMENT_MODE", "false").lower() == "true":
        print_console_debug()
            
    # Clear candidates list for next document
    _escalated_candidates = []

def get_gpt_classification(text: str, context: str) -> dict:
    """
    Retrieves the Stage 2 classification from cache, if present.
    """
    return _gpt_cache.get((text, context))

def get_document_metrics(doc_id: str = "UNKNOWN") -> dict:
    """
    Returns aggregation metrics for the current document.
    """
    total = _total_candidates_processed
    escalated = len(_gpt_cache)
    esc_rate = round((escalated / total) * 100, 1) if total > 0 else 0.0
    return {
        "document_id": doc_id,
        "total_candidates": total,
        "escalated_candidates": escalated,
        "escalation_rate": esc_rate
    }
