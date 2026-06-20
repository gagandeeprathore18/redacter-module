import sys
import json
import os

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs"
)
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "redaction_audit.json")

def main():
    if len(sys.argv) < 2:
        print("Usage: python audit_lookup.py <candidate_name>")
        sys.exit(1)
        
    query = sys.argv[1].strip()
    if not os.path.exists(AUDIT_LOG_FILE):
        print("Error: No redaction audit log file found.")
        sys.exit(1)
        
    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        print(f"Error reading audit log file: {e}")
        sys.exit(1)
        
    # Find matching events
    matches = []
    for entry in logs:
        cand = entry.get("candidate", "")
        if query.lower() in cand.lower():
            matches.append(entry)
            
    if not matches:
        print(f"No audit logs found matching candidate: '{query}'")
        sys.exit(0)
        
    # Construct a trace report
    print(f"=== Audit Trail for Candidate: '{query}' ===")
    
    # Organize matches by exact candidate
    by_candidate = {}
    for entry in matches:
        cand = entry.get("candidate")
        if cand not in by_candidate:
            by_candidate[cand] = []
        by_candidate[cand].append(entry)
        
    for cand, events in by_candidate.items():
        print(f"\nCandidate: {cand}")
        print("-" * (len(cand) + 11))
        for ev in events:
            stage = ev.get("stage")
            timestamp = ev.get("timestamp", "")
            
            details = {k: v for k, v in ev.items() if k not in ("candidate", "stage", "timestamp")}
            print(f"  [{timestamp}] Stage: {stage}")
            for k, v in details.items():
                print(f"    {k}: {v}")
    print("\n=============================================")

if __name__ == "__main__":
    main()
