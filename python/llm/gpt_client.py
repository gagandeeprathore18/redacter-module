import os
import json
import urllib.request
import urllib.error
import time
import datetime
from datetime import datetime as dt

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'config', 'llm_config.json'
)

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "model": "gpt-4o-mini",
        "confidence_threshold": 70.0,
        "pricing": {
            "input_cost_per_million": 0.15,
            "output_cost_per_million": 0.60
        },
        "telemetry_log_path": os.path.join(os.path.dirname(__file__), "telemetry.log"),
        "monthly_stats_path": os.path.join(os.path.dirname(__file__), "monthly_stats.json")
    }

def log_telemetry_passive(doc_id, escalated_count, prompt_tokens, completion_tokens, cost, duration_ms, model):
    pass

def update_monthly_stats_passive(escalated_count, prompt_tokens, completion_tokens, cost):
    try:
        config = load_config()
        stats_path = config.get("monthly_stats_path")
        current_month = dt.utcnow().strftime("%Y-%m")
        
        stats = {}
        if os.path.exists(stats_path):
            with open(stats_path, 'r') as f:
                stats = json.load(f)
                
        month_data = stats.get(current_month, {
            "month": current_month,
            "documents_processed": 0,
            "total_escalations": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost_usd": 0.0
        })
        
        month_data["documents_processed"] += 1
        month_data["total_escalations"] += escalated_count
        month_data["prompt_tokens"] += prompt_tokens
        month_data["completion_tokens"] += completion_tokens
        month_data["total_cost_usd"] = round(month_data["total_cost_usd"] + cost, 6)
        
        stats[current_month] = month_data
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass

def load_env_file():
    if os.environ.get("TESTING") == "true":
        return
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_paths = [
        os.path.join(root_path, ".env"),
        os.path.join(root_path, "branding", ".env")
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip().strip("'\"")
            except Exception:
                pass

load_env_file()

# Temporary startup validation log
if os.environ.get("OPENAI_API_KEY"):
    print("OPENAI_API_KEY loaded successfully")
else:
    print("OPENAI_API_KEY is not set in the environment")

def get_openai_api_key():
    return os.environ.get("OPENAI_API_KEY")

def call_gpt_verification(candidates, issuing_university, doc_id="UNKNOWN"):
    """
    Submits a batch of escalated candidates to GPT-4o Mini for semantic review.
    Returns: a dict mapping candidate ID -> classification result dict.
    """
    if not candidates:
        return {}

    api_key = get_openai_api_key()
    if not api_key:
        print("Warning: OPENAI_API_KEY environment variable not found. Skipping Stage 2 GPT verification.")
        return {}

    config = load_config()
    model = os.environ.get("OPENAI_MODEL", config.get("model", "gpt-4o-mini"))
    pricing = config.get("pricing", {"input_cost_per_million": 0.15, "output_cost_per_million": 0.60})
    
    # Phase 4: GPT Batch Classification (max 20 candidates per request)
    chunk_size = 20
    candidate_chunks = [candidates[i:i + chunk_size] for i in range(0, len(candidates), chunk_size)]
    
    # Phase 5: System Prompt for Context-Aware Date and Entity Classification
    system_prompt = (
        "You are an academic document classifier.\n"
        "Classify each candidate into exactly one classification:\n"
        "PERSON\n"
        "ACADEMIC_TITLE\n"
        "SUBMISSION_EVENT\n"
        "PROTECTED_SECTION\n"
        "UNIVERSITY_BRANDING\n"
        "ACADEMIC_CONTENT\n"
        "ADMINISTRATIVE_DATE\n"
        "ACADEMIC_DATE\n\n"
        "Return JSON format containing a list of objects under key 'candidates'.\n"
        "Each object must have exactly:\n"
        "{\n"
        "  \"id\": int,\n"
        "  \"date\": string,\n"
        "  \"classification\": string,\n"
        "  \"action\": \"REDACT\" | \"PRESERVE\",\n"
        "  \"reason\": string\n"
        "}\n"
        "For PERSON, UNIVERSITY_BRANDING, UNIVERSITY_ENTITY, METADATA_FIELD, BUSINESS_FIELD, ADMINISTRATIVE_DATE, action must be REDACT.\n"
        "For ACADEMIC_TITLE, SUBMISSION_EVENT, PROTECTED_SECTION, ACADEMIC_CONTENT, ACADEMIC_DATE, action must be PRESERVE.\n"
        "Do not return explanations outside the json."
    )
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    total_duration_ms = 0
    out_map = {}
    
    for chunk in candidate_chunks:
        # Phase 6: Compact Payload Format
        user_payload = {
            "issuing_university": issuing_university or "UNKNOWN",
            "candidates": [
                {
                    "id": c["id"],
                    "candidate": c["candidate"],
                    "context": c["context"]
                }
                for c in chunk
            ]
        }
        
        payload_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }
        
        # Phase 6 Log: GPT Requests
        try:
            from redaction.redaction_audit import RedactionAudit
            for c in chunk:
                RedactionAudit.log({
                    "candidate": c["candidate"],
                    "stage": "GPT_REQUEST"
                })
        except Exception:
            pass

        start_time = time.time()
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload_data).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            # 180 seconds timeout
            with urllib.request.urlopen(req, timeout=180) as response:
                res_data = response.read().decode("utf-8")
                duration_ms = int((time.time() - start_time) * 1000)
                total_duration_ms += duration_ms
                
                res_json = json.loads(res_data)
                
                # Extract usage
                usage = res_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                
                # Calculate cost
                input_cost = (prompt_tokens / 1_000_000.0) * pricing.get("input_cost_per_million", 0.15)
                output_cost = (completion_tokens / 1_000_000.0) * pricing.get("output_cost_per_million", 0.60)
                cost = input_cost + output_cost
                total_cost += cost
                
                # Parse results (Phase 9: Minimal GPT Response Format)
                content_str = res_json["choices"][0]["message"]["content"]
                results_data = json.loads(content_str)
                
                items = results_data.get("candidates") or results_data.get("results") or []
                for r in items:
                    out_map[r["id"]] = {
                        "classification": r.get("classification"),
                        "confidence": r.get("confidence", 100),
                        "action": r.get("action"),
                        "reason": r.get("reason")
                    }

                # Phase 6 Log: GPT Responses
                try:
                    from redaction.redaction_audit import RedactionAudit
                    num_cands = len(chunk)
                    prompt_tokens_per_cand = prompt_tokens // num_cands if num_cands > 0 else 0
                    completion_tokens_per_cand = completion_tokens // num_cands if num_cands > 0 else 0
                    id_to_cand = {c["id"]: c["candidate"] for c in chunk}
                    
                    for r in items:
                        cand_id = r.get("id")
                        classification = r.get("classification")
                        if cand_id in id_to_cand:
                            RedactionAudit.log({
                                "candidate": id_to_cand[cand_id],
                                "stage": "GPT_RESPONSE",
                                "classification": classification,
                                "prompt_tokens": prompt_tokens_per_cand,
                                "completion_tokens": completion_tokens_per_cand
                            })
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: GPT semantic verification request failed for chunk: {e}")
            
    # Log telemetry passively for the entire document run
    log_telemetry_passive(doc_id, len(candidates), total_prompt_tokens, total_completion_tokens, total_cost, total_duration_ms, model)
    update_monthly_stats_passive(len(candidates), total_prompt_tokens, total_completion_tokens, total_cost)
    
    return out_map, {
        "prompt_tokens": total_prompt_tokens, 
        "completion_tokens": total_completion_tokens, 
        "cost": total_cost, 
        "duration_ms": total_duration_ms
    }
