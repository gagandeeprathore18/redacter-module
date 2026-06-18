import unittest
from unittest.mock import patch, MagicMock
import os
import json
import tempfile
import sys

os.environ["TESTING"] = "true"

# Ensure root and python directories are in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'python'))

from redaction.escalation_manager import (
    clear_cache, get_escalation_reasons, register_candidate_scan, run_gpt_review
)

class TestEscalationAudit(unittest.TestCase):

    def setUp(self):
        clear_cache()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch_logs_dir = patch('redaction.escalation_manager.LOGS_DIR', self.temp_dir.name)
        self.patch_logs_dir.start()
        os.environ["OPENAI_API_KEY"] = "mock_key"

    def tearDown(self):
        self.patch_logs_dir.stop()
        self.temp_dir.cleanup()
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        clear_cache()

    def test_get_escalation_reasons_low_confidence(self):
        reasons = get_escalation_reasons("John Connor", "Module Lead: John Connor", "PERSON", "REDACT", 45.0, [])
        self.assertIn("LOW_CONFIDENCE", reasons)

    def test_get_escalation_reasons_high_impact_action(self):
        reasons = get_escalation_reasons("Confidentiality", "Do not share.", "UNKNOWN", "REDACT", 50.0, [])
        self.assertIn("HIGH_IMPACT_ACTION", reasons)

    def test_get_escalation_reasons_unknown_pattern(self):
        reasons = get_escalation_reasons("Strategic Business Management", "Topic: Strategic Business Management", "UNKNOWN", "KEEP", 0.0, [])
        self.assertIn("UNKNOWN_PATTERN", reasons)

    @patch('urllib.request.urlopen')
    def test_audit_logs_and_analytics_persistence(self, mock_urlopen):
        # Setup mock API response with telemetry
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50
            },
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "results": [
                            {"id": 1, "classification": "ACADEMIC_TITLE", "confidence": 95}
                        ]
                    })
                }
            }]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Register candidate
        register_candidate_scan("Strategic Business Project Management", "Topic: Strategic Business Project Management", "UNKNOWN", "KEEP", 0.0, [])

        # Run Stage 2 GPT review
        run_gpt_review("Buckinghamshire New University", "doc_test_123")

        # Verify document log was created in our temp directory
        doc_log_path = os.path.join(self.temp_dir.name, "escalations", "doc_test_123.json")
        self.assertTrue(os.path.exists(doc_log_path))
        
        with open(doc_log_path, "r") as f:
            data = json.load(f)
            self.assertEqual(data["document_id"], "doc_test_123")
            self.assertEqual(data["escalated_candidates"], 1)
            self.assertEqual(data["escalation_breakdown"]["UNKNOWN_PATTERN"], 1)
            self.assertEqual(data["candidates"][0]["candidate"], "Strategic Business Project Management")
            self.assertEqual(data["candidates"][0]["gpt_prediction"], "ACADEMIC_TITLE")
            self.assertEqual(data["candidates"][0]["final_classification"], "ACADEMIC_TITLE")

        # Verify global analytics store was created/updated
        analytics_path = os.path.join(self.temp_dir.name, "escalation_analytics.json")
        self.assertTrue(os.path.exists(analytics_path))
        
        with open(analytics_path, "r") as f:
            analytics = json.load(f)
            self.assertEqual(analytics["escalation_frequencies"]["Strategic Business Project Management"], 1)
            self.assertEqual(analytics["python_gpt_disagreements"]["UNKNOWN → ACADEMIC_TITLE"], 1)

if __name__ == '__main__':
    unittest.main()
