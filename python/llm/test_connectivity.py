import os
import sys
import time

# Ensure import paths are set up correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.gpt_client import call_gpt_verification

def main():
    print("Starting connectivity test to GPT-4o Mini...")
    candidates = [
        {
            "id": 1,
            "candidate": "Claire Ngo",
            "context": "Module Leader: Claire Ngo",
            "python_prediction": "PERSON",
            "python_confidence": 95
        }
    ]
    
    start_time = time.time()
    result, telemetry = call_gpt_verification(candidates, "Buckinghamshire New University", "CONNECTIVITY_TEST")
    end_time = time.time()
    
    duration = (end_time - start_time) * 1000
    
    if result:
        print(f"Request Status: SUCCESS")
        print(f"Response Time: {duration:.2f} ms")
        print(f"Result: {result}")
        
        # Read the last line of the telemetry.log to get token usage
        telemetry_path = os.path.join(os.path.dirname(__file__), "telemetry.log")
        if os.path.exists(telemetry_path):
            with open(telemetry_path, "r") as f:
                lines = f.readlines()
                if lines:
                    import json
                    last_entry = json.loads(lines[-1].strip())
                    print(f"Token Usage - Prompt: {last_entry.get('prompt_tokens')}, Completion: {last_entry.get('completion_tokens')}, Total: {last_entry.get('total_tokens')}")
    else:
        print("Request Status: FAILURE")
        print("Could not retrieve classification. Check key or network connectivity.")

if __name__ == "__main__":
    main()
