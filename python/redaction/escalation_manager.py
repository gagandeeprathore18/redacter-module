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
        "FRAGMENT_CONTENT": 0
    },
    "rejected_candidates": []
}

def clear_cache():
    global _escalated_candidates, _candidate_counter, _gpt_cache, _total_candidates_processed
    global _document_id, _audit_records, _escalation_breakdown, _filter_report
    _gpt_cache = {}
    _escalated_candidates = []
    _candidate_counter = 0
    _total_candidates_processed = 0
    _document_id = "UNKNOWN"
    _audit_records = {}
    _escalation_breakdown = {
        "LOW_CONFIDENCE": 0,
        "CLASSIFIER_CONFLICT": 0,
        "UNKNOWN_PATTERN": 0,
        "HIGH_IMPACT_ACTION": 0,
        "UNIVERSITY_BRANDING_VERIFICATION": 0
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
            "FRAGMENT_CONTENT": 0
        },
        "rejected_candidates": []
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

    # 1. LOW_CONFIDENCE
    if 0 < score < threshold and classification in ("PERSON", "UNIVERSITY_ENTITY", "BUSINESS_FIELD"):
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

def register_candidate_scan(text: str, context: str, classification: str, action: str, score: float, reasons: list):
    """
    Registers a candidate during Stage 1 scan pass. If it requires escalation,
    accumulates it for the batch GPT request.
    """
    global _candidate_counter, _total_candidates_processed, _filter_report
    _total_candidates_processed += 1
    
    key = (text, context)
    if key in _gpt_cache:
        return

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
                    "warnings": warnings
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
            action = "REDACT" if final_class in ("PERSON", "UNIVERSITY_BRANDING", "SUBMISSION_EVENT") else "PRESERVE"
            
            if action == "REDACT":
                from redaction.sensitivity_score import get_sensitivity_score
                from redaction.redaction_validator import validate_redaction
                
                # Check sensitivity score
                if get_sensitivity_score(final_class) < 70:
                    action = "PRESERVE"
                # Check redaction validator
                elif not validate_redaction(cand["candidate"], final_class):
                    action = "PRESERVE"
                    final_class = "ACADEMIC_CONTENT"
                    
            if cand_id in gpt_results and action == "PRESERVE" and gpt_pred in ("PERSON", "UNIVERSITY_BRANDING", "SUBMISSION_EVENT"):
                gpt_results[cand_id]["classification"] = final_class
                gpt_results[cand_id]["confidence"] = 0
                
            audit["final_classification"] = final_class
            audit["action"] = action

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
