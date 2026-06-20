import json
import re

with open("logs/redaction_audit.json", "r") as f:
    logs = json.load(f)

doc_ids = {e.get("document_id") for e in logs if e.get("document_id")}
print("Unique Document IDs in logs:")
for doc_id in sorted(doc_ids):
    print(f"- {doc_id}")
