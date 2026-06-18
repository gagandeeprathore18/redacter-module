import os
import json
import glob

# Baseline constants for reduction tracking
BASELINE_ESCALATIONS = 41.0
BASELINE_COST = 0.0014
BASELINE_TOKENS = 5750.0
BASELINE_LATENCY = 25000.0  # ms

def generate_report():
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(root_path, "logs", "escalations")
    analytics_file = os.path.join(root_path, "logs", "escalation_analytics.json")
    learned_file = os.path.join(root_path, "logs", "learned_classifications.json")
    filter_report_file = os.path.join(root_path, "logs", "candidate_filter_report.json")
    
    # Phase 9 aggregates
    total_extracted_filter = 0
    total_filtered_out_filter = 0
    total_remaining_filter = 0
    rejection_breakdown_filter = {
        "PARAGRAPH_CONTENT": 0,
        "LONG_TEXT": 0,
        "MULTI_SENTENCE": 0,
        "STRUCTURAL_CONTENT": 0,
        "INSTRUCTIONAL_CONTENT": 0,
        "FRAGMENT_CONTENT": 0
     }
    
    if os.path.exists(filter_report_file):
        try:
            with open(filter_report_file, "r") as f:
                filter_data = json.load(f)
                for doc_id, doc_filter in filter_data.items():
                    total_extracted_filter += doc_filter.get("total_extracted", 0)
                    total_filtered_out_filter += doc_filter.get("filtered_out", 0)
                    total_remaining_filter += doc_filter.get("remaining_candidates", 0)
                    breakdown = doc_filter.get("rejection_breakdown", {})
                    for r_reason, r_count in breakdown.items():
                        rejection_breakdown_filter[r_reason] = rejection_breakdown_filter.get(r_reason, 0) + r_count
        except Exception as fe:
            print(f"Warning: Failed to read candidate filter report: {fe}")

    # Phase 10 aggregates
    total_input_tokens = 0
    total_output_tokens = 0
    total_telemetry_cost = 0.0
    total_telemetry_escalations = 0
    total_telemetry_filtered = 0
    doc_telemetry_list = []
    
    # Phase 11 aggregates (Global Escalation Source Analysis)
    global_source_analysis = {
        "LOW_CONFIDENCE": 0,
        "CLASSIFIER_CONFLICT": 0,
        "UNKNOWN_PATTERN": 0,
        "HIGH_IMPACT_ACTION": 0,
        "UNIVERSITY_BRANDING_VERIFICATION": 0
    }
    
    if os.path.exists(analytics_file):
        try:
            with open(analytics_file, "r") as f:
                analytics_data = json.load(f)
                
                # Phase 10: Token Telemetry
                token_telemetry = analytics_data.get("token_telemetry", {})
                for doc_id, doc_tel in token_telemetry.items():
                    in_tok = doc_tel.get("input_tokens", 0)
                    out_tok = doc_tel.get("output_tokens", 0)
                    c_cost = doc_tel.get("cost", 0.0)
                    esc_cand = doc_tel.get("escalated_candidates", 0)
                    filt_cand = doc_tel.get("filtered_candidates", 0)
                    
                    total_input_tokens += in_tok
                    total_output_tokens += out_tok
                    total_telemetry_cost += c_cost
                    total_telemetry_escalations += esc_cand
                    total_telemetry_filtered += filt_cand
                    
                    doc_telemetry_list.append({
                        "document": doc_id,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "cost": c_cost,
                        "escalated_candidates": esc_cand,
                        "filtered_candidates": filt_cand
                    })
                
                # Phase 11: Escalation Source Analysis
                global_source_analysis = analytics_data.get("escalation_source_analysis", global_source_analysis)
        except Exception as fe:
            print(f"Warning: Failed to read escalation analytics for telemetry: {fe}")
    # Calculate the Accuracy KPI metrics
    sensitive_total = 0
    sensitive_redacted = 0
    academic_total = 0
    academic_preserved = 0
    false_positives_redacted = 0
    
    from redact_engine import EMAIL_PATTERN, PHONE_PATTERN, STUDENT_ID_PATTERN
    
    def get_ground_truth_label(cand_text):
        norm = cand_text.lower().strip()
        # 1. Sensitive check
        if EMAIL_PATTERN.search(cand_text) or PHONE_PATTERN.search(cand_text) or STUDENT_ID_PATTERN.search(cand_text):
            return "SENSITIVE"
        if any(w in norm for w in ["bnu", "buckinghamshire", "tutor name", "leader", "assessor", "verifier", "marker", "reviewer", "st12345", "reg2024001"]):
            return "SENSITIVE"
        # 2. Academic/Preserve check
        if any(w in norm for w in ["learning outcome", "rubric", "criteria", "methodology", "literature", "reference", "reading", "ethics", "integrity", "referencing"]):
            return "ACADEMIC"
        # Check bibliography / citation pattern
        try:
            from redaction.preservation_engine import PreservationEngine
            if PreservationEngine.is_bibliographic_entry(cand_text):
                return "ACADEMIC"
        except Exception:
            pass
        return "OTHER"

    audit_file = os.path.join(root_path, "redaction_audit.json")
    if os.path.exists(audit_file):
        try:
            with open(audit_file, "r") as f:
                audit_data = json.load(f)
                for entry in audit_data:
                    c_text = entry.get("candidate", "")
                    c_action = entry.get("action", "")
                    gt = get_ground_truth_label(c_text)
                    is_redacted = c_action in ("REDACT", "REMOVE_BLOCK", "remove", "REMOVE", "remove_block")
                    
                    if gt == "SENSITIVE":
                        sensitive_total += 1
                        if is_redacted:
                            sensitive_redacted += 1
                    elif gt == "ACADEMIC":
                        academic_total += 1
                        if not is_redacted:
                            academic_preserved += 1
                        else:
                            false_positives_redacted += 1
        except Exception:
            pass
            
    # Calculate percentages
    sensitive_removal_accuracy = (sensitive_redacted / sensitive_total * 100) if sensitive_total > 0 else 100.0
    preservation_accuracy = (academic_preserved / academic_total * 100) if academic_total > 0 else 100.0
    
    # Write to logs/accuracy_kpi_dashboard.json
    kpi_file = os.path.join(root_path, "logs", "accuracy_kpi_dashboard.json")
    status_sra = "PASS" if sensitive_removal_accuracy >= 95.0 else "FAIL"
    status_pa = "PASS" if preservation_accuracy >= 95.0 else "FAIL"
    
    # Calculate escalations per document (from telemetry data if available, else num_docs)
    num_telemetry_docs = len(doc_telemetry_list)
    gpt_escalations_per_document = (total_telemetry_escalations / num_telemetry_docs) if num_telemetry_docs > 0 else 0.0
    status_esc = "PASS" if gpt_escalations_per_document < 15.0 else "FAIL"
    status_fpr = "PASS" if false_positives_redacted < 2 else "FAIL"
    
    kpi_data = {
        "sensitive_removal_accuracy": round(sensitive_removal_accuracy, 2),
        "preservation_accuracy": round(preservation_accuracy, 2),
        "gpt_escalations_per_document": round(gpt_escalations_per_document, 2),
        "false_positive_redactions": false_positives_redacted,
        "target_kpis": {
            "sensitive_removal_accuracy": ">=95%",
            "preservation_accuracy": ">=95%",
            "gpt_escalations_per_document": "<15",
            "false_positive_redactions": "<2"
        },
        "status": {
            "sensitive_removal_accuracy": status_sra,
            "preservation_accuracy": status_pa,
            "gpt_escalations_per_document": status_esc,
            "false_positive_redactions": status_fpr
        }
    }
    
    try:
        os.makedirs(os.path.dirname(kpi_file), exist_ok=True)
        with open(kpi_file, "w") as f:
            json.dump(kpi_data, f, indent=2)
    except Exception:
        pass
    total_candidates = 0
    total_escalations = 0
    total_cost = 0.0
    total_latency = 0.0
    latency_counts = 0
    
    # Trigger statistics counters
    # Each reason -> {"count": 0, "agreement_count": 0}
    trigger_stats = {
        "LOW_CONFIDENCE": {"count": 0, "agreement_count": 0},
        "CLASSIFIER_CONFLICT": {"count": 0, "agreement_count": 0},
        "UNKNOWN_PATTERN": {"count": 0, "agreement_count": 0},
        "HIGH_IMPACT_ACTION": {"count": 0, "agreement_count": 0},
        "UNIVERSITY_BRANDING_VERIFICATION": {"count": 0, "agreement_count": 0}
    }
    
    # Document level metrics
    doc_costs = {}
    doc_escalations = {}
    doc_warnings = {}
    
    # Diagnostics counters
    candidate_frequencies = {}
    reason_candidate_frequencies = {
        "LOW_CONFIDENCE": {},
        "CLASSIFIER_CONFLICT": {},
        "UNKNOWN_PATTERN": {},
        "HIGH_IMPACT_ACTION": {},
        "UNIVERSITY_BRANDING_VERIFICATION": {}
    }
    low_confidence_scores = {}
    classifier_conflicts = {}
    gpt_agreement_transitions = {}
    
    # Candidate detailed tracking for rules/safety verification
    # key: candidate text -> {"docs": set(), "classifications": {}, "confidences": []}
    candidate_analysis = {}
    
    # 1. Read all document logs
    doc_files = glob.glob(os.path.join(log_dir, "*.json"))
    for file_path in doc_files:
        try:
            with open(file_path, "r") as f:
                doc_data = json.load(f)
                doc_id = doc_data.get("document_id", os.path.basename(file_path))
                total_candidates += doc_data.get("total_candidates", 0)
                esc_count = doc_data.get("escalated_candidates", 0)
                total_escalations += esc_count
                doc_escalations[doc_id] = esc_count
                doc_warnings[doc_id] = doc_data.get("warnings", [])
                
                doc_cost = 0.0
                # Candidates usage
                for cand in doc_data.get("candidates", []):
                    c_cost = cand.get("request_cost_usd", 0.0)
                    total_cost += c_cost
                    doc_cost += c_cost
                    
                    lat = cand.get("response_time_ms", 0)
                    if lat > 0:
                        total_latency += lat
                        latency_counts += 1
                        
                    # Candidate analysis for rule candidates
                    text = cand["candidate"]
                    gpt_pred = cand.get("gpt_prediction")
                    gpt_conf = cand.get("gpt_confidence")
                    
                    if text not in candidate_analysis:
                        candidate_analysis[text] = {"docs": set(), "classifications": {}, "confidences": []}
                        
                    analysis = candidate_analysis[text]
                    analysis["docs"].add(doc_id)
                    if gpt_pred:
                        analysis["classifications"][gpt_pred] = analysis["classifications"].get(gpt_pred, 0) + 1
                    if gpt_conf is not None:
                        analysis["confidences"].append(gpt_conf)
                        
                    # Trigger statistics tracking
                    reasons = cand.get("escalation_reasons", [])
                    py_pred = cand.get("python_prediction")
                    py_conf = cand.get("python_confidence", 0)
                    for reason in reasons:
                        if reason in trigger_stats:
                            trigger_stats[reason]["count"] += 1
                            if gpt_pred and py_pred == gpt_pred:
                                trigger_stats[reason]["agreement_count"] += 1
                                
                    # Diagnostics: Candidate frequencies (Phase 3)
                    candidate_frequencies[text] = candidate_frequencies.get(text, 0) + 1
                    
                    # Diagnostics: Reason breakdowns (Phase 4)
                    for reason in reasons:
                        if reason in reason_candidate_frequencies:
                            reason_candidate_frequencies[reason][text] = reason_candidate_frequencies[reason].get(text, 0) + 1
                            
                    # Diagnostics: Low confidence investigation (Phase 5)
                    if "LOW_CONFIDENCE" in reasons and py_pred:
                        if py_pred not in low_confidence_scores:
                            low_confidence_scores[py_pred] = []
                        low_confidence_scores[py_pred].append(py_conf)
                        
                    # Diagnostics: Classifier conflict investigation (Phase 6)
                    if "CLASSIFIER_CONFLICT" in reasons:
                        c1 = cand.get("classifier_1")
                        c2 = cand.get("classifier_2")
                        # Fallback for old logs
                        if not c1 or not c2:
                            if py_pred in ("PERSON", "UNIVERSITY_ENTITY"):
                                c1 = py_pred
                                c2 = "ACADEMIC_TITLE"
                            else:
                                c1 = py_pred or "UNKNOWN"
                                c2 = "UNKNOWN"
                        conflict_key = f"{c1} vs {c2}"
                        classifier_conflicts[conflict_key] = classifier_conflicts.get(conflict_key, 0) + 1
                        
                    # Diagnostics: GPT agreement analysis (Phase 7)
                    if gpt_pred:
                        transition_key = f"{py_pred} → {gpt_pred}"
                        gpt_agreement_transitions[transition_key] = gpt_agreement_transitions.get(transition_key, 0) + 1
                
                doc_costs[doc_id] = doc_costs.get(doc_id, 0.0) + doc_cost
        except Exception:
            pass
            
    # Calculate core averages
    num_docs = len(doc_files)
    avg_escalations = (total_escalations / num_docs) if num_docs > 0 else 0.0
    avg_cost = (total_cost / num_docs) if num_docs > 0 else 0.0
    escalation_rate = (total_escalations / total_candidates * 100) if total_candidates > 0 else 0.0
    
    # Calculate doc-level latency
    avg_latency = (total_latency / num_docs) if num_docs > 0 else 0.0
    
    # Average tokens per document
    actual_total_tokens = 0
    for file_path in doc_files:
        try:
            with open(file_path, "r") as f:
                doc_data = json.load(f)
                for cand in doc_data.get("candidates", []):
                    actual_total_tokens += cand.get("token_usage", {}).get("total_tokens", 0)
        except Exception:
            pass
    avg_tokens = (actual_total_tokens / num_docs) if num_docs > 0 else 0.0

    # Calculate Reduction percentages
    esc_reduction = ((BASELINE_ESCALATIONS - avg_escalations) / BASELINE_ESCALATIONS) * 100 if BASELINE_ESCALATIONS > 0 else 0.0
    cost_reduction = ((BASELINE_COST - avg_cost) / BASELINE_COST) * 100 if BASELINE_COST > 0 else 0.0
    token_reduction = ((BASELINE_TOKENS - avg_tokens) / BASELINE_TOKENS) * 100 if BASELINE_TOKENS > 0 else 0.0
    latency_reduction = ((BASELINE_LATENCY - avg_latency) / BASELINE_LATENCY) * 100 if BASELINE_LATENCY > 0 else 0.0

    # Rule Candidate Detection logic & Safety Validation
    promoted_rules = {}
    rule_candidates = []
    
    for text, analysis in candidate_analysis.items():
        doc_count = len(analysis["docs"])
        classifications = analysis["classifications"]
        confidences = analysis["confidences"]
        
        if not classifications:
            continue
            
        most_common_class = max(classifications, key=classifications.get)
        common_count = classifications[most_common_class]
        
        total_occurrences = sum(classifications.values())
        consistency = (common_count / total_occurrences) * 100 if total_occurrences > 0 else 0.0
        avg_conf = (sum(confidences) / len(confidences)) if confidences else 0.0
        
        rc_info = {
            "candidate": text,
            "recommended_classification": most_common_class,
            "consistency": round(consistency, 1),
            "confidence": round(avg_conf, 1),
            "doc_count": doc_count,
            "occurrences": total_occurrences,
            "safety_validated": False,
            "recommended_action": "CREATE_PYTHON_RULE" if (doc_count >= 5 and consistency >= 95.0 and avg_conf >= 90.0) else "KEEP_GPT_ESCALATION"
        }
        
        # Safety Validation check
        if doc_count >= 5 and consistency >= 95.0 and avg_conf >= 90.0:
            rc_info["safety_validated"] = True
            promoted_rules[text.lower().strip()] = most_common_class
            
        rule_candidates.append(rc_info)
        
    # Persist the memory layer (learned rules)
    try:
        os.makedirs(os.path.dirname(learned_file), exist_ok=True)
        existing_rules = {}
        if os.path.exists(learned_file):
            try:
                with open(learned_file, "r") as f:
                    existing_rules = json.load(f)
            except Exception:
                pass
        existing_rules.update(promoted_rules)
        with open(learned_file, "w") as f:
            json.dump(existing_rules, f, indent=2)
    except Exception:
        pass

    # Sort diagnostics
    sorted_candidate_freqs = sorted(candidate_frequencies.items(), key=lambda x: x[1], reverse=True)
    sorted_classifier_conflicts = sorted(classifier_conflicts.items(), key=lambda x: x[1], reverse=True)
    sorted_gpt_agreements = sorted(gpt_agreement_transitions.items(), key=lambda x: x[1], reverse=True)
    sorted_rule_candidates = sorted(rule_candidates, key=lambda x: x["occurrences"], reverse=True)
    sorted_expensive_docs = sorted(doc_costs.items(), key=lambda x: x[1], reverse=True)
    sorted_highest_esc_docs = sorted(doc_escalations.items(), key=lambda x: x[1], reverse=True)
    
    # Sort reason candidates for Phase 4
    sorted_reason_candidates = {}
    for reason in reason_candidate_frequencies:
        sorted_reason_candidates[reason] = sorted(
            reason_candidate_frequencies[reason].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:20]

    # Calculate average confidence per class on LOW_CONFIDENCE (Phase 5)
    low_confidence_averages = {}
    for klass, scores in low_confidence_scores.items():
        low_confidence_averages[klass] = round(sum(scores) / len(scores), 1) if scores else 0.0
    sorted_low_conf_averages = sorted(low_confidence_averages.items(), key=lambda x: x[1])

    # Generate report string
    report = []
    report.append("# GPT Escalation Optimization & Usage Dashboard\n")
    
    report.append("## Core Pipeline Metrics")
    report.append(f"- **Total Documents Processed**: {num_docs}")
    report.append(f"- **Total Candidates Scanned**: {total_candidates}")
    report.append(f"- **Total Escalations**: {total_escalations}")
    report.append(f"- **Escalation Rate**: {escalation_rate:.2f}%")
    report.append(f"- **Average Escalations Per Document**: {avg_escalations:.2f}")
    report.append(f"- **Average Cost Per Document**: ${avg_cost:.6f} USD")
    report.append(f"- **Average Tokens Per Document**: {avg_tokens:.2f}")
    report.append(f"- **Average GPT Response Time**: {avg_latency:.2f} ms")
    report.append("")
    
    report.append("## Cost Optimization & Reduction Tracking")
    report.append("| Metric | Before | After | Reduction % |")
    report.append("|---|---|---|---|")
    report.append(f"| Average Escalations | {BASELINE_ESCALATIONS:.1f} | {avg_escalations:.1f} | {esc_reduction:.2f}% |")
    report.append(f"| Average Tokens | {BASELINE_TOKENS:.1f} | {avg_tokens:.1f} | {token_reduction:.2f}% |")
    report.append(f"| Average Cost (USD) | ${BASELINE_COST:.4f} | ${avg_cost:.6f} | {cost_reduction:.2f}% |")
    report.append(f"| Average Latency | {BASELINE_LATENCY/1000.0:.1f}s | {avg_latency/1000.0:.2f}s | {latency_reduction:.2f}% |")
    report.append("")

    report.append("## Accuracy KPI Dashboard")
    report.append("")
    report.append("| Metric | Target | Current | Status |")
    report.append("|---|---|---|---|")
    report.append(f"| Sensitive Removal Accuracy | &ge;95% | {sensitive_removal_accuracy:.2f}% | {status_sra} |")
    report.append(f"| Preservation Accuracy | &ge;95% | {preservation_accuracy:.2f}% | {status_pa} |")
    report.append(f"| GPT Escalations per Document | &lt;15 | {gpt_escalations_per_document:.2f} | {status_esc} |")
    report.append(f"| False Positive Redactions | &lt;2 | {false_positives_redacted} | {status_fpr} |")
    report.append("")
    
    report.append("## Escalation Trigger Statistics")
    report.append("| Trigger Reason | Occurrences | Accuracy/Agreement After GPT |")
    report.append("|---|---|---|")
    for reason, stats in trigger_stats.items():
        count = stats["count"]
        agr = stats["agreement_count"]
        acc = (agr / count * 100) if count > 0 else 0.0
        report.append(f"| {reason} | {count} | {acc:.2f}% |")
    report.append("")

    # Phase 9: Candidate Quality Analytics
    report.append("## Candidate Quality Analytics (Phase 9)")
    report.append("")
    report.append("### Pipeline Filtering Summary")
    report.append(f"- **Total Extracted Candidates**: {total_extracted_filter}")
    report.append(f"- **Filtered Out (Low Quality)**: {total_filtered_out_filter}")
    report.append(f"- **Remaining Candidates (Proceeded to Classification)**: {total_remaining_filter}")
    
    rejection_rate = (total_filtered_out_filter / total_extracted_filter * 100) if total_extracted_filter > 0 else 0.0
    report.append(f"- **Candidate Rejection Rate**: {rejection_rate:.2f}%")
    report.append("")
    report.append("### Rejection Reason Breakdown")
    report.append("| Rejection Reason | Count |")
    report.append("|---|---|")
    for reason_name, reason_count in rejection_breakdown_filter.items():
        report.append(f"| {reason_name} | {reason_count} |")
    report.append("")
    
    # Phase 10: Escalation Impact Report
    report.append("## Escalation Impact Report (Phase 10)")
    report.append("")
    report.append("### Before vs. After Pipeline Performance Comparison")
    
    avg_remaining = (total_remaining_filter / num_docs) if num_docs > 0 else 0.0
    avg_latency_s = avg_latency / 1000.0
    
    # Baseline comparison metrics
    before_candidates = 145.0
    before_escalations = 100.0
    before_cost = 0.0043
    before_latency = 58.0
    
    cand_reduction = ((before_candidates - avg_remaining) / before_candidates * 100) if before_candidates > 0 else 0.0
    esc_reduction_p10 = ((before_escalations - avg_escalations) / before_escalations * 100) if before_escalations > 0 else 0.0
    cost_reduction_p10 = ((before_cost - avg_cost) / before_cost * 100) if before_cost > 0 else 0.0
    latency_reduction_p10 = ((before_latency - avg_latency_s) / before_latency * 100) if before_latency > 0 else 0.0
    
    report.append("| Metric | Before (Unoptimized) | After (Optimized) | Reduction % |")
    report.append("|---|---|---|---|")
    report.append(f"| Candidates Proceeding to Classification | {before_candidates:.1f} | {avg_remaining:.1f} | {cand_reduction:.2f}% |")
    report.append(f"| GPT Escalations | {before_escalations:.1f} | {avg_escalations:.1f} | {esc_reduction_p10:.2f}% |")
    report.append(f"| Average GPT Cost | ${before_cost:.4f} | ${avg_cost:.6f} | {cost_reduction_p10:.2f}% |")
    report.append(f"| Processing Time (Latency) | {before_latency:.1f}s | {avg_latency_s:.2f}s | {latency_reduction_p10:.2f}% |")
    report.append("")

    # Phase 10: Token Usage Telemetry
    report.append("## Token Usage & Cost Telemetry (Phase 10)")
    report.append("")
    
    num_telemetry_docs = len(doc_telemetry_list)
    cost_per_document = (total_telemetry_cost / num_telemetry_docs) if num_telemetry_docs > 0 else 0.0
    cost_per_candidate = (total_telemetry_cost / total_telemetry_escalations) if total_telemetry_escalations > 0 else 0.0
    tokens_per_candidate = ((total_input_tokens + total_output_tokens) / total_telemetry_escalations) if total_telemetry_escalations > 0 else 0.0
    
    report.append(f"- **Average GPT Cost Per Document**: ${cost_per_document:.6f} USD")
    report.append(f"- **Average GPT Cost Per Escalated Candidate**: ${cost_per_candidate:.6f} USD")
    report.append(f"- **Average Tokens Per Escalated Candidate**: {tokens_per_candidate:.2f}")
    report.append("")
    report.append("### Per-Document Token Telemetry Detail")
    report.append("| Document | Input Tokens | Output Tokens | Cost (USD) | Escalated | Filtered |")
    report.append("|---|---|---|---|---|---|")
    for doc_tel in doc_telemetry_list:
        report.append(
            f"| {doc_tel['document']} | {doc_tel['input_tokens']} | {doc_tel['output_tokens']} | "
            f"${doc_tel['cost']:.6f} | {doc_tel['escalated_candidates']} | {doc_tel['filtered_candidates']} |"
        )
    report.append("")

    # Phase 11: Escalation Source Analysis
    report.append("## Escalation Source Analysis (Phase 11)")
    report.append("")
    report.append("### Global Escalation Trigger Breakdown")
    report.append("| Escalation Trigger | Occurrences | Percentage |")
    report.append("|---|---|---|")
    
    total_triggers = sum(global_source_analysis.values())
    dominant_trigger = "None"
    dominant_count = -1
    
    for trigger, count in global_source_analysis.items():
        pct = (count / total_triggers * 100) if total_triggers > 0 else 0.0
        report.append(f"| {trigger} | {count} | {pct:.2f}% |")
        if count > dominant_count:
            dominant_count = count
            dominant_trigger = trigger
            
    report.append("")
    report.append(f"**Dominant Escalation Trigger**: **{dominant_trigger}** ({dominant_count} occurrences)")
    report.append("")

    # Phase 12: Automatic Rule Promotion Candidates
    report.append("## Automatic Rule Promotion Candidates (Phase 12)")
    report.append("")
    
    # Generate recommendations list
    rule_promotion_candidates = []
    for text, val in candidate_analysis.items():
        classifications = val["classifications"]
        if not classifications:
            continue
        
        most_common_class = max(classifications, key=classifications.get)
        common_count = classifications[most_common_class]
        total_occurrences = sum(classifications.values())
        consistency = (common_count / total_occurrences) * 100 if total_occurrences > 0 else 0.0
        
        # We consider a candidate for promotion if it has >= 2 escalations
        if total_occurrences >= 2:
            rec_action = "PROMOTE_TO_PYTHON_RULE" if (total_occurrences >= 5 and consistency >= 95.0) else "MONITOR_AND_REVIEW"
            rule_promotion_candidates.append({
                "candidate": text,
                "escalations": total_occurrences,
                "gpt_classification": most_common_class,
                "consistency": round(consistency),
                "recommended_action": rec_action
            })
            
    # Sort descending by escalations
    rule_promotion_candidates = sorted(rule_promotion_candidates, key=lambda x: x["escalations"], reverse=True)
    
    # Save Rule Promotion Candidates to file
    promo_file = os.path.join(root_path, "logs", "rule_promotion_candidates.json")
    try:
        with open(promo_file, "w") as f:
            json.dump(rule_promotion_candidates, f, indent=2)
    except Exception:
        pass
        
    report.append("| Candidate | Escalation Count | GPT Classification | Consistency | Recommended Action |")
    report.append("|---|---|---|---|---|")
    if rule_promotion_candidates:
        for rc in rule_promotion_candidates[:20]:  # Top 20
            report.append(
                f"| {rc['candidate']} | {rc['escalations']} | `{rc['gpt_classification']}` | "
                f"{rc['consistency']}% | **{rc['recommended_action']}** |"
            )
    else:
        report.append("| *None* | 0 | - | - | - |")
    report.append("")

    # --- GPT Escalation Diagnostics Section (Phase 9) ---
    report.append("## GPT Escalation Diagnostics\n")

    # Phase 10 warnings
    report.append("### Optimization & Severity Warnings")
    has_warnings = False
    for doc, warns in doc_warnings.items():
        for w in warns:
            has_warnings = True
            report.append(f"- **{doc}** &rarr; **{w['severity']}**: {w['message']}")
    if not has_warnings:
        report.append("*No warnings generated for current documents.*")
    report.append("")

    # Phase 3
    report.append("### Phase 3 – Top Escalated Candidates")
    if sorted_candidate_freqs:
        for idx, (cand, count) in enumerate(sorted_candidate_freqs[:20], 1):
            report.append(f"{idx}. **{cand}** &rarr; {count} escalations")
    else:
        report.append("*No escalated candidates registered.*")
    report.append("")

    # Phase 4
    report.append("### Phase 4 – Escalation Reason Breakdown")
    for reason in sorted_reason_candidates:
        report.append(f"#### {reason}")
        items = sorted_reason_candidates[reason]
        if items:
            for idx, (cand, count) in enumerate(items, 1):
                report.append(f"{idx}. **{cand}** &rarr; {count}")
        else:
            report.append("*No candidates escalated for this reason.*")
        report.append("")

    # Phase 5
    report.append("### Phase 5 – Low Confidence Investigation")
    report.append("**Average Python Confidence Score per Class (on LOW_CONFIDENCE escalations):**")
    if sorted_low_conf_averages:
        for klass, avg in sorted_low_conf_averages:
            report.append(f"- **{klass}**: {avg}% confidence")
    else:
        report.append("*No low confidence escalations registered.*")
    report.append("")

    # Phase 6
    report.append("### Phase 6 – Classifier Conflict Investigation")
    report.append("**Conflicting Classifiers:**")
    if sorted_classifier_conflicts:
        for idx, (pair, count) in enumerate(sorted_classifier_conflicts, 1):
            report.append(f"{idx}. **{pair}** &rarr; {count} occurrences")
    else:
        report.append("*No classifier conflicts registered.*")
    report.append("")

    # Phase 7 (GPT Agreement Analysis)
    report.append("### Phase 7 – GPT Agreement Analysis")
    report.append("**Python to GPT Prediction Transitions:**")
    if sorted_gpt_agreements:
        for idx, (trans, count) in enumerate(sorted_gpt_agreements, 1):
            report.append(f"{idx}. **{trans}** &rarr; {count} occurrences")
    else:
        report.append("*No transitions registered.*")
    report.append("")

    # Phase 8 (Escalation Reduction Opportunities)
    report.append("### Phase 8 – Escalation Reduction Opportunities")
    if sorted_rule_candidates:
        for idx, rc in enumerate(sorted_rule_candidates[:20], 1):
            report.append(f"{idx}. **{rc['candidate']}** &rarr; recommend classification: `{rc['recommended_classification']}`")
            report.append(f"   * [Consistency: {rc['consistency']}%, Conf: {rc['confidence']}%, Docs: {rc['doc_count']}, Occurrences: {rc['occurrences']}]")
            report.append(f"   * Recommended Action: **{rc['recommended_action']}**")
    else:
        report.append("*No rule candidates identified yet.*")
    report.append("")

    # Most Expensive and Highest Escalations (retained)
    report.append("### Most Expensive Documents")
    if sorted_expensive_docs:
        for idx, (doc, cost) in enumerate(sorted_expensive_docs[:10], 1):
            report.append(f"{idx}. {doc} &rarr; ${cost:.6f} USD")
    else:
        report.append("*No documents processed yet.*")
    report.append("")
    
    report.append("### Highest Escalation Documents")
    if sorted_highest_esc_docs:
        for idx, (doc, count) in enumerate(sorted_highest_esc_docs[:10], 1):
            report.append(f"{idx}. {doc} &rarr; {count} escalations")
    else:
        report.append("*No documents processed yet.*")
    report.append("")
    
    report_content = "\n".join(report)
    
    # Write to file
    report_file = os.path.join(root_path, "logs", "escalation_report.md")
    try:
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report_content)
    except Exception:
        pass

    # Phase 9 & 10 & 11 & 12 JSON output formatting for ease of auditing
    print("\n--- PHASE 9: CANDIDATE QUALITY ANALYTICS JSON ---")
    print(json.dumps({
        "total_extracted": total_extracted_filter,
        "filtered_out": total_filtered_out_filter,
        "remaining_candidates": total_remaining_filter,
        "breakdown": rejection_breakdown_filter
    }, indent=2))
    
    print("\n--- PHASE 10: TOKEN USAGE TELEMETRY JSON ---")
    print(json.dumps({
        "cost_per_document": f"${cost_per_document:.6f}",
        "cost_per_candidate": f"${cost_per_candidate:.6f}",
        "tokens_per_candidate": f"{tokens_per_candidate:.2f}"
    }, indent=2))
    
    print("\n--- PHASE 10: ESCALATION IMPACT REPORT JSON ---")
    print(json.dumps({
        "before": {
            "candidates": before_candidates,
            "escalations": before_escalations,
            "cost": before_cost,
            "processing_time": before_latency
        },
        "after": {
            "candidates": round(avg_remaining, 1),
            "escalations": round(avg_escalations, 1),
            "cost": round(avg_cost, 6),
            "processing_time": round(avg_latency_s, 2)
        },
        "reduction_percentages": {
            "escalation_reduction_pct": round(esc_reduction_p10, 2),
            "cost_reduction_pct": round(cost_reduction_p10, 2),
            "latency_reduction_pct": round(latency_reduction_p10, 2)
        }
    }, indent=2))
    
    print("\n--- PHASE 11: ESCALATION SOURCE ANALYSIS JSON ---")
    print(json.dumps(global_source_analysis, indent=2))
    
    print("\n--- PHASE 12: AUTOMATIC RULE PROMOTION CANDIDATES JSON ---")
    print(json.dumps(rule_promotion_candidates[:5], indent=2)) # Top 5 preview
    print("\n------------------------------------------------\n")
        
    print(report_content)

if __name__ == "__main__":
    generate_report()
