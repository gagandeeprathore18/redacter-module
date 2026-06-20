import json
import os
import time
import threading
from datetime import datetime

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs"
)
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "redaction_audit.json")
ACCURACY_REVIEW_FILE = os.path.join(LOGS_DIR, "accuracy_review.json")

_lock = threading.Lock()

class RedactionAudit:
    @staticmethod
    def clear():
        """Clear all audit logs from the file."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        with _lock:
            try:
                with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            except Exception as e:
                print(f"[RedactionAudit] Clear failed: {e}")

def determine_source_and_rule(entry: dict) -> tuple[str, str]:
    import re
    classifier = entry.get("classifier", "")
    stage = entry.get("stage", "")
    reason = entry.get("reason", "")
    source_det = entry.get("source_detector", "")
    cand = entry.get("candidate", "")
    classification = entry.get("classification", "")
    
    source = "manual_rule"
    matched_rule = "unknown_rule"
    
    if "gpt" in str(classifier).lower() or "gpt" in str(reason).lower() or "gpt" in str(source_det).lower():
        source = "gpt_classifier"
        matched_rule = "gpt_escalation_review"
        return source, matched_rule

    if stage == "HEADING_FILTER" or "heading" in str(reason).lower() or "heading" in str(classifier).lower():
        source = "heading_detector"
        matched_rule = reason or classifier or "heading_detector_rule"
        return source, matched_rule
        
    if stage == "STRUCTURAL_FILTER" or "structural" in str(reason).lower():
        source = "heading_detector"
        matched_rule = reason or "structural_content_rule"
        return source, matched_rule
        
    if stage == "PARAGRAPH_FILTER" or "paragraph" in str(reason).lower():
        source = "paragraph_detector"
        matched_rule = "paragraph_content_check"
        return source, matched_rule
        
    if stage == "GRADING_BAND_FILTER" or "grading_band" in str(reason).lower():
        source = "rubric_detector"
        matched_rule = "grading_band_detector_rule"
        return source, matched_rule
        
    if stage == "RUBRIC_FILTER" or "rubric" in str(reason).lower():
        source = "rubric_detector"
        matched_rule = "rubric_pattern_detector_rule"
        return source, matched_rule

    rule_str = str(classifier or reason or source_det or "").lower()
    
    if "metadata" in rule_str:
        source = "metadata_detector"
        matched_rule = classifier or reason or "metadata_label_dictionary"
    elif "date" in rule_str or "time" in rule_str or "datetime" in rule_str:
        source = "date_time_detector"
        matched_rule = "date_time_value_redaction"
    elif "person" in rule_str or "name" in rule_str or "tutor" in rule_str or "assessor" in rule_str or "verifier" in rule_str:
        source = "person_detector"
        matched_rule = classifier or reason or "person_name_rule"
    elif "university" in rule_str or "uni" in rule_str or "bucks" in rule_str or "oxford" in rule_str:
        source = "university_detector"
        matched_rule = classifier or reason or "university_branding_rule"
    elif "regex" in rule_str or "pattern" in rule_str or "email" in rule_str or "phone" in rule_str or "student_id" in rule_str or "postal" in rule_str:
        source = "regex_engine"
        matched_rule = classifier or reason or source_det or "regex_pattern_match"
    elif "business" in rule_str:
        source = "regex_engine"
        matched_rule = classifier or reason or "business_field_rule"
        
    return source, matched_rule

class RedactionAudit:
    @staticmethod
    def clear():
        """Clear all audit logs from the file."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        with _lock:
            try:
                with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
            except Exception as e:
                print(f"[RedactionAudit] Clear failed: {e}")

    @staticmethod
    def log(entry: dict):
        """
        Logs an audit event to logs/redaction_audit.json.
        Adds a timestamp if not present.
        """
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
            
        # Standardize trace object
        if "text" not in entry:
            entry["text"] = entry.get("candidate", "")
        if "decision" not in entry:
            entry["decision"] = entry.get("decision", entry.get("action", ""))
        
        # Normalize decision to REDACT, ESCALATE, or KEEP
        decision_raw = str(entry.get("decision", "")).upper()
        if "ESCALATE" in decision_raw:
            entry["decision"] = "ESCALATE"
        elif "REDACT" in decision_raw or "REMOVE" in decision_raw:
            entry["decision"] = "REDACT"
        else:
            entry["decision"] = "KEEP"
            
        if "classification" not in entry:
            entry["classification"] = entry.get("classification", "UNKNOWN")
            
        # Determine source and matched_rule
        source, matched_rule = determine_source_and_rule(entry)
        if "source" not in entry or not entry["source"]:
            entry["source"] = source
        if "matched_rule" not in entry or not entry["matched_rule"]:
            entry["matched_rule"] = matched_rule
            
        if "confidence" not in entry:
            entry["confidence"] = entry.get("confidence", entry.get("score", 0))
            
        if "gpt_involved" not in entry:
            entry["gpt_involved"] = "gpt" in str(entry.get("classifier", "")).lower() or \
                                    "gpt" in str(entry.get("reason", "")).lower() or \
                                    "gpt" in str(entry.get("source_detector", "")).lower() or \
                                    entry.get("gpt_used", False)
                                    
        if "page" not in entry:
            entry["page"] = entry.get("page", None)
            
        if "document_id" not in entry:
            entry["document_id"] = entry.get("document_id", os.environ.get("CURRENT_DOCUMENT_ID", ""))
            
        os.makedirs(LOGS_DIR, exist_ok=True)
        with _lock:
            existing = []
            if os.path.exists(AUDIT_LOG_FILE):
                try:
                    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = []
                except Exception:
                    existing = []
            
            existing.append(entry)
            
            try:
                with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[RedactionAudit] Log failed: {e}")

    @staticmethod
    def get_all_logs() -> list:
        """Get all logged entries."""
        if not os.path.exists(AUDIT_LOG_FILE):
            return []
        with _lock:
            try:
                with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    @staticmethod
    def generate_lifecycle_report() -> dict:
        """
        Phase 9 - Create Candidate Lifecycle Report.
        Groups log events by candidate and builds a summary of which stages were touched.
        """
        logs = RedactionAudit.get_all_logs()
        report = {}
        header_images_detected = 0
        header_images_removed = 0
        address_blocks_detected = 0
        address_blocks_removed = 0
        contact_blocks_removed = 0

        for entry in logs:
            cand = entry.get("candidate")
            if not cand:
                continue
            
            # Count header redactions
            stage = entry.get("stage", "")
            cls = entry.get("classification", "")
            decision = entry.get("decision", "")
            if stage == "HEADER_REDACTION":
                if cls == "HEADER_IMAGE":
                    header_images_detected += 1
                    if decision == "REDACT":
                        header_images_removed += 1
                elif cls == "ADDRESS_BLOCK":
                    address_blocks_detected += 1
                    if decision == "REDACT":
                        address_blocks_removed += 1
                elif cls == "CONTACT_BLOCK":
                    if decision == "REDACT":
                        contact_blocks_removed += 1
            
            if cand not in report:
                report[cand] = {
                    "candidate": cand,
                    "extracted": False,
                    "heading_filter": False,
                    "structural_filter": False,
                    "preservation_engine": False,
                    "escalated": False,
                    "gpt_used": False,
                    "redacted": False
                }
            
            stage = entry.get("stage")
            decision = entry.get("decision")
            
            if stage == "EXTRACTED":
                report[cand]["extracted"] = True
            elif stage == "HEADING_FILTER":
                report[cand]["heading_filter"] = True
            elif stage == "STRUCTURAL_FILTER":
                report[cand]["structural_filter"] = True
            elif stage == "PRESERVATION_ENGINE":
                report[cand]["preservation_engine"] = True
                if decision == "PRESERVED":
                    report[cand]["redacted"] = False
            elif stage == "ESCALATION_CHECK":
                if decision == "ESCALATE":
                    report[cand]["escalated"] = True
            elif stage in ("GPT_REQUEST", "GPT_RESPONSE"):
                report[cand]["gpt_used"] = True
            elif stage == "FINAL_DECISION":
                if decision == "REDACT":
                    report[cand]["redacted"] = True
                else:
                    report[cand]["redacted"] = False
                    
        return report

    @staticmethod
    def generate_accuracy_review(expected_decisions: dict = None):
        """
        Phase 10 - Create Accuracy Review File (logs/accuracy_review.json).
        Compares expected vs actual redaction decisions to identify False Positives/False Negatives.
        """
        if expected_decisions is None:
            expected_decisions = {}
            
        lifecycle = RedactionAudit.generate_lifecycle_report()
        reviews = []
        
        for cand, info in lifecycle.items():
            expected = expected_decisions.get(cand)
            if not expected:
                # Fallback heuristics or skip
                continue
                
            actual = "REDACT" if info["redacted"] else "PRESERVE"
            if expected == "PRESERVE" and actual == "REDACT":
                reviews.append({
                    "candidate": cand,
                    "expected": "PRESERVE",
                    "actual": "REDACT",
                    "error_type": "FALSE_POSITIVE"
                })
            elif expected == "REDACT" and actual == "PRESERVE":
                reviews.append({
                    "candidate": cand,
                    "expected": "REDACT",
                    "actual": "PRESERVE",
                    "error_type": "FALSE_NEGATIVE"
                })
                
        os.makedirs(LOGS_DIR, exist_ok=True)
        with _lock:
            try:
                with open(ACCURACY_REVIEW_FILE, "w", encoding="utf-8") as f:
                    json.dump(reviews, f, indent=2)
            except Exception as e:
                print(f"[RedactionAudit] Accuracy Review failed: {e}")

    @staticmethod
    def generate_summary(doc_id: str) -> dict:
        """
        Phase 11 - Create Audit Summary Generator.
        Generates document-level stats, decision sources, and preservation sources.
        """
        logs = RedactionAudit.get_all_logs()
        
        # Filter logs for the specific document if doc_id is provided
        if doc_id:
            logs = [entry for entry in logs if entry.get("document_id") == doc_id]
            
        total_candidates = 0
        redacted_count = 0
        preserved_count = 0
        skipped_count = 0
        gpt_escalated_count = 0
        
        paragraph_candidates_removed = 0
        grading_band_matches = 0
        rubric_matches = 0
        rubric_sections_preserved = 0
        
        header_images_detected = 0
        header_images_removed = 0
        address_blocks_detected = 0
        address_blocks_removed = 0
        contact_blocks_removed = 0
        
        metadata_fields_detected = set()
        metadata_fields_redacted = set()
        business_fields_detected = set()
        business_fields_redacted = set()
        date_time_fields_detected = set()
        date_time_fields_detected = set()
        date_time_fields_redacted = set()
        
        dates_detected_set = set()
        dates_sent_to_gpt_set = set()
        dates_redacted_set = set()
        historical_dates_auto_preserved_set = set()
        time_values_redacted_set = set()
        
        # Track candidate classifications
        cand_classes = {}
        
        decision_sources = {}
        preservation_sources = {}
        
        # Track unique candidates
        unique_cands = set()
        cands_redacted = set()
        cands_preserved = set()
        cands_skipped = set()
        
        # Track counts of redacted candidate text and sources
        redaction_source_counts = {}
        term_counts = {}
        cand_sources = {}
        
        for entry in logs:
            cand = entry.get("candidate")
            if not cand:
                continue
            
            unique_cands.add(cand)
            stage = entry.get("stage")
            decision = entry.get("decision")
            reason = entry.get("reason")
            classification = entry.get("classification")
            source_detector = entry.get("source_detector", "")
            
            if stage == "CLASSIFICATION" and classification:
                cand_classes[cand] = classification
                if classification == "METADATA_FIELD":
                    metadata_fields_detected.add(cand)
                elif classification == "BUSINESS_FIELD":
                    business_fields_detected.add(cand)
                elif classification in ("DATE_TIME_VALUE", "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE", "ACADEMIC_DATE"):
                    date_time_fields_detected.add(cand)

            if source_detector == "DATE_CANDIDATE_PATTERN" or classification in ("DATE_CANDIDATE", "ADMINISTRATIVE_DATE", "ACADEMIC_DATE"):
                dates_detected_set.add(cand)
            if stage == "HISTORICAL_DATE_FILTER":
                historical_dates_auto_preserved_set.add(cand)
            if stage == "ESCALATION_CHECK" and decision == "ESCALATE" and (source_detector == "DATE_CANDIDATE_PATTERN" or classification == "DATE_CANDIDATE"):
                dates_sent_to_gpt_set.add(cand)
            
            # Count telemetry metrics
            if stage == "PARAGRAPH_FILTER" or reason == "PARAGRAPH_CONTENT":
                paragraph_candidates_removed += 1
            if stage == "GRADING_BAND_FILTER" or reason == "GRADING_BAND":
                grading_band_matches += 1
            if stage == "RUBRIC_FILTER" or reason == "RUBRIC_CONTENT":
                rubric_matches += 1
                rubric_sections_preserved += 1
            elif stage == "PRESERVATION_ENGINE" and reason == "RUBRIC_CONTENT":
                rubric_sections_preserved += 1
                
            if stage == "HEADER_REDACTION":
                if classification == "HEADER_IMAGE":
                    header_images_detected += 1
                    if decision == "REDACT":
                        header_images_removed += 1
                elif classification == "ADDRESS_BLOCK":
                    address_blocks_detected += 1
                    if decision == "REDACT":
                        address_blocks_removed += 1
                elif classification == "CONTACT_BLOCK":
                    if decision == "REDACT":
                        contact_blocks_removed += 1
                
            if stage == "EXTRACTED":
                pass
            elif stage in ("HEADING_FILTER", "STRUCTURAL_FILTER"):
                if decision == "REJECTED":
                    cands_skipped.add(cand)
                    preservation_sources[reason or stage] = preservation_sources.get(reason or stage, 0) + 1
            elif stage in ("PRESERVATION_ENGINE", "PARAGRAPH_FILTER", "GRADING_BAND_FILTER", "RUBRIC_FILTER"):
                if decision == "PRESERVED":
                    cands_preserved.add(cand)
                    preservation_sources[reason or stage] = preservation_sources.get(reason or stage, 0) + 1
            elif stage == "ESCALATION_CHECK" and decision == "ESCALATE":
                gpt_escalated_count += 1
            elif stage == "FINAL_DECISION" or stage == "GPT_RESPONSE" or decision == "REDACT":
                # Ensure we capture source and final outcome
                source = entry.get("source", entry.get("decision_source", "UNKNOWN"))
                cls = cand_classes.get(cand, entry.get("classification"))
                if decision == "REDACT":
                    cands_redacted.add(cand)
                    cand_sources[cand] = source
                    text = entry.get("text", cand)
                    term_counts[text] = term_counts.get(text, 0) + 1
                    
                    decision_sources[source] = decision_sources.get(source, 0) + 1
                    if cls == "METADATA_FIELD":
                        metadata_fields_redacted.add(cand)
                        metadata_fields_detected.add(cand)
                    elif cls == "BUSINESS_FIELD":
                        business_fields_redacted.add(cand)
                        business_fields_detected.add(cand)
                    elif cls in ("DATE_TIME_VALUE", "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE", "ACADEMIC_DATE"):
                        date_time_fields_redacted.add(cand)
                        date_time_fields_detected.add(cand)
                    
                    if source_detector == "DATE_CANDIDATE_PATTERN" or cls in ("DATE_CANDIDATE", "ADMINISTRATIVE_DATE"):
                        dates_redacted_set.add(cand)
                    if source_detector == "TIME_VAL_PATTERN" or cls == "TIME_VALUE":
                        time_values_redacted_set.add(cand)
                else:
                    cands_preserved.add(cand)
                    # Track preservation source
                    preservation_sources[source] = preservation_sources.get(source, 0) + 1
                    if cls == "METADATA_FIELD":
                        metadata_fields_detected.add(cand)
                    elif cls == "BUSINESS_FIELD":
                        business_fields_detected.add(cand)
                    elif cls in ("DATE_TIME_VALUE", "DATE_CANDIDATE", "TIME_VALUE", "ADMINISTRATIVE_DATE", "ACADEMIC_DATE"):
                        date_time_fields_detected.add(cand)
                        
        # Final pass over unique redacted candidates to build precise source counts
        for cand in cands_redacted:
            src = cand_sources.get(cand, "manual_rule")
            redaction_source_counts[src] = redaction_source_counts.get(src, 0) + 1
            
        total_candidates = len(unique_cands)
        redacted_count = len(cands_redacted)
        skipped_count = len(cands_skipped)
        
        # Candidates that are in unique_cands but not redacted/skipped are preserved
        preserved_count = len(unique_cands - cands_redacted - cands_skipped)
        
        # Build academic lists
        def is_academic_content(text: str) -> bool:
            if not text:
                return False
            norm = text.lower().strip()
            try:
                from redaction.preservation_engine import PRESERVE_PATTERNS, CATEGORY_KEYWORDS
                for pat in PRESERVE_PATTERNS:
                    if pat in norm:
                        return True
                for keywords in CATEGORY_KEYWORDS.values():
                    for kw in keywords:
                        if kw in norm:
                            return True
            except Exception:
                pass
            academic_indicators = [
                "module", "rubric", "grade", "grading", "assessment", "learning outcome",
                "ethics", "integrity", "referencing", "methodology", "literature review",
                "pass = ", "fail = ", "distinction", "merit", "coursework", "assignment"
            ]
            for ind in academic_indicators:
                if ind in norm:
                    return True
            return False

        preserved_academic_content = []
        redacted_academic_content = []
        for cand in unique_cands:
            if is_academic_content(cand):
                if cand in cands_redacted:
                    redacted_academic_content.append(cand)
                else:
                    preserved_academic_content.append(cand)
                    
        top_redacted_terms = dict(sorted(term_counts.items(), key=lambda x: x[1], reverse=True))
        
        total_redactions = redacted_count
        metadata_redactions = len(metadata_fields_redacted)
        business_field_redactions = len(business_fields_redacted)
        
        summary = {
            "document": doc_id,
            "header_images_detected": header_images_detected,
            "header_images_removed": header_images_removed,
            "address_blocks_detected": address_blocks_detected,
            "address_blocks_removed": address_blocks_removed,
            "contact_blocks_removed": contact_blocks_removed,
            "legacy_submission_patterns_removed": True,
            "total_candidates": total_candidates,
            "redacted": redacted_count,
            "preserved": preserved_count,
            "skipped": skipped_count,
            "gpt_escalated": gpt_escalated_count,
            "decision_sources": decision_sources,
            "preservation_sources": preservation_sources,
            "metadata_fields_detected": len(metadata_fields_detected),
            "metadata_fields_redacted": metadata_redactions,
            "business_fields_detected": len(business_fields_detected),
            "business_fields_redacted": business_field_redactions,
            "date_time_values_detected": len(date_time_fields_detected),
            "date_time_values_redacted": len(date_time_fields_redacted),
            "dates_detected": len(dates_detected_set),
            "dates_sent_to_gpt": len(dates_sent_to_gpt_set),
            "dates_redacted": len(dates_redacted_set),
            "dates_preserved": len(dates_detected_set - dates_redacted_set),
            "historical_dates_auto_preserved": len(historical_dates_auto_preserved_set),
            "time_values_redacted": len(time_values_redacted_set),
            "total_redactions": total_redactions,
            "metadata_redactions": metadata_redactions,
            "business_field_redactions": business_field_redactions,
            "redaction_source_counts": redaction_source_counts,
            "top_redacted_terms": top_redacted_terms,
            "preserved_academic_content": preserved_academic_content,
            "redacted_academic_content": redacted_academic_content,
            "paragraph_candidates_removed": paragraph_candidates_removed,
            "grading_band_matches": grading_band_matches,
            "rubric_matches": rubric_matches,
            "rubric_sections_preserved": rubric_sections_preserved,
            "quality_dashboard": {
                "total_redactions": total_redactions,
                "metadata_redactions": metadata_redactions,
                "business_field_redactions": business_field_redactions,
                "paragraph_candidates_removed": paragraph_candidates_removed,
                "grading_band_matches": grading_band_matches,
                "rubric_matches": rubric_matches,
                "rubric_sections_preserved": rubric_sections_preserved,
                "dates_detected": len(dates_detected_set),
                "dates_sent_to_gpt": len(dates_sent_to_gpt_set),
                "dates_redacted": len(dates_redacted_set),
                "dates_preserved": len(dates_detected_set - dates_redacted_set),
                "historical_dates_auto_preserved": len(historical_dates_auto_preserved_set),
                "time_values_redacted": len(time_values_redacted_set)
            }
        }
        return summary
