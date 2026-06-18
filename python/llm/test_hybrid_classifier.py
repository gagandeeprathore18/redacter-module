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
    clear_cache, check_escalation_criteria, register_candidate_scan,
    run_gpt_review, get_gpt_classification, get_document_metrics
)
from redaction.entity_classifier import classify_entity
from llm.gpt_client import load_config, call_gpt_verification

class TestHybridClassifier(unittest.TestCase):

    def setUp(self):
        clear_cache()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "llm_config.json")
        self.telemetry_path = os.path.join(self.temp_dir.name, "telemetry.log")
        self.stats_path = os.path.join(self.temp_dir.name, "monthly_stats.json")
        
        # Set environment variable
        os.environ["OPENAI_API_KEY"] = "mock_key"
        
        # Write temporary config
        self.config_data = {
            "model": "gpt-4o-mini",
            "confidence_threshold": 70.0,
            "pricing": {
                "input_cost_per_million": 0.15,
                "output_cost_per_million": 0.60
            },
            "telemetry_log_path": self.telemetry_path,
            "monthly_stats_path": self.stats_path
        }
        with open(self.config_path, 'w') as f:
            json.dump(self.config_data, f)
            
        # Patch configuration file path in client/manager
        self.patch_config = patch('llm.gpt_client.CONFIG_FILE', self.config_path)
        self.patch_config.start()

    def tearDown(self):
        self.patch_config.stop()
        self.temp_dir.cleanup()
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        clear_cache()

    def test_deterministic_rules(self):
        # 1. Person Prefix Rules
        cls, act, _, scr = classify_entity("Claire Ngo", "Tutor Name: Claire Ngo")
        self.assertEqual(cls, "PERSON")
        self.assertEqual(act, "REDACT")
        self.assertEqual(scr, 100)

        # 2. Submission Event Rules
        cls, act, _, scr = classify_entity("Draft Submission")
        self.assertEqual(cls, "SUBMISSION_EVENT")
        self.assertEqual(act, "REDACT")
        self.assertEqual(scr, 100)

        # 3. Protected Section Rules
        cls, act, _, scr = classify_entity("Recommended Reading")
        self.assertEqual(cls, "PROTECTED_SECTION")
        self.assertEqual(act, "KEEP")
        self.assertEqual(scr, 100)

    def test_escalation_criteria_low_confidence(self):
        # Escalate low confidence person
        self.assertTrue(check_escalation_criteria(
            text="Managing Innovation",
            context="Tutor is Managing Innovation",
            classification="PERSON",
            action="REDACT",
            score=45.0,
            reasons=[]
        ))

        # Do not escalate high confidence person
        self.assertFalse(check_escalation_criteria(
            text="Claire Ngo",
            context="Module Leader: Claire Ngo",
            classification="PERSON",
            action="REDACT",
            score=91.0,
            reasons=[]
        ))

    def test_escalation_criteria_unknown_capitalized(self):
        # Escalate capitalized phrase categorized as UNKNOWN
        self.assertTrue(check_escalation_criteria(
            text="Strategic Digital Transformation",
            context="Topic: Strategic Digital Transformation",
            classification="UNKNOWN",
            action="KEEP",
            score=0,
            reasons=[]
        ))

        # Do not escalate lowercase UNKNOWN text
        self.assertFalse(check_escalation_criteria(
            text="and other standard items",
            context="rules and other standard items",
            classification="UNKNOWN",
            action="KEEP",
            score=0,
            reasons=[]
        ))

    def test_escalation_criteria_conflict(self):
        # Disagreement between name scoring and academic title detector
        self.assertTrue(check_escalation_criteria(
            text="Managing Innovation",
            context="Managing Innovation",
            classification="PERSON",
            action="REDACT",
            score=90,
            reasons=["academic_term_detected"]
        ))

    def test_escalation_criteria_high_impact(self):
        # Escalate confidentiality if about to redact/remove but score is low
        self.assertTrue(check_escalation_criteria(
            text="Confidentiality",
            context="Section: Confidentiality",
            classification="PROTECTED_SECTION",
            action="REMOVE_BLOCK",
            score=50,
            reasons=[]
        ))

    @patch('urllib.request.urlopen')
    def test_batch_gpt_review_and_caching(self, mock_urlopen):
        # Setup mock API response
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
                            {"id": 1, "classification": "ACADEMIC_TITLE", "confidence": 95},
                            {"id": 2, "classification": "PERSON", "confidence": 98}
                        ]
                    })
                }
            }]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Register candidates to scan - use non-excl name "Strategic Innovation Management"
        register_candidate_scan("Strategic Innovation Management", "context 1", "PERSON", "REDACT", 45, [])
        register_candidate_scan("Claire Ngo", "Module Leader: Claire Ngo", "PERSON", "REDACT", 95, []) # High confidence, not escalated
        register_candidate_scan("Integrating Technological and Organizational Change", "context 3", "UNKNOWN", "KEEP", 0, [])
 
        # Verify metrics shows 2 escalated candidates out of 3 total registered
        metrics = get_document_metrics("doc-123")
        self.assertEqual(metrics["total_candidates"], 3)
        self.assertEqual(metrics["escalated_candidates"], 2)
 
        # Run Stage 2 GPT review
        run_gpt_review("Buckinghamshire New University", "doc-123")
 
        # Verify cache overrides Stage 1 classification and maps to policy
        # 1. "Strategic Innovation Management" -> GPT ACADEMIC_TITLE -> KEEP
        cls, act, _, scr = classify_entity("Strategic Innovation Management", "context 1")
        self.assertEqual(cls, "ACADEMIC_TITLE")
        self.assertEqual(act, "KEEP")
        self.assertEqual(scr, 95)
 
        # 2. "Integrating Technological and Organizational Change" -> GPT PERSON -> REDACT
        cls, act, _, scr = classify_entity("Integrating Technological and Organizational Change", "context 3")
        self.assertEqual(cls, "PERSON")
        self.assertEqual(act, "REDACT")
        self.assertEqual(scr, 98)

        # 3. "Claire Ngo" -> (not escalated, falls back to original prediction)
        cls, act, _, scr = classify_entity("Claire Ngo", "Module Leader: Claire Ngo")
        self.assertEqual(cls, "PERSON")
        self.assertEqual(act, "REDACT")

    @patch('urllib.request.urlopen')
    def test_passive_analytics_and_fallback(self, mock_urlopen):
        # Test error fallback (network failure)
        mock_urlopen.side_effect = Exception("OpenAI API unreachable")

        # Use "John Connor" (valid name with context, will score > 50 in Stage 1)
        register_candidate_scan("John Connor", "Module Lead: John Connor", "PERSON", "REDACT", 65, [])
        
        # Executing the review must not throw an exception (passive constraint)
        try:
            run_gpt_review("Buckinghamshire New University", "doc-123")
        except Exception as e:
            self.fail(f"run_gpt_review threw an exception on failure: {e}")

        # Cached classification falls back gracefully to Stage 1 python classification ("PERSON")
        cls, act, _, scr = classify_entity("John Connor", "Module Lead: John Connor")
        self.assertEqual(cls, "PERSON")
        self.assertEqual(act, "REDACT")

    def test_branding_escalation_rules(self):
        from redaction.ownership_manager import (
            determine_issuing_university, clear_issuing_university,
            clear_detected_universities, register_detected_university
        )
        clear_issuing_university()
        clear_detected_universities()

        # 1. No issuing university identified from logo -> Should escalate
        self.assertTrue(check_escalation_criteria(
            text="Harvard University",
            context="Harvard University",
            classification="UNIVERSITY_ENTITY",
            action="REDACT",
            score=90,
            reasons=[]
        ))

        # 2. Issuing university identified, single university name matching it -> Should NOT escalate
        determine_issuing_university("savversk logo") # Buckinghamshire New University
        clear_detected_universities()
        register_detected_university("Buckinghamshire New University")
        
        self.assertFalse(check_escalation_criteria(
            text="Buckinghamshire New University",
            context="Buckinghamshire New University",
            classification="UNIVERSITY_ENTITY",
            action="REDACT",
            score=90,
            reasons=[]
        ))

        # 3. Multiple unique universities appear -> Should escalate
        register_detected_university("University of Oxford")
        self.assertTrue(check_escalation_criteria(
            text="Buckinghamshire New University",
            context="Buckinghamshire New University",
            classification="UNIVERSITY_ENTITY",
            action="REDACT",
            score=90,
            reasons=[]
        ))

    def test_conflict_attribution_diagnostics(self):
        # Disagreement between name scoring and academic title detector conflict attribution
        register_candidate_scan(
            text="Managing Innovation",
            context="Managing Innovation",
            classification="PERSON",
            action="REDACT",
            score=90,
            reasons=["academic_term_detected"]
        )
        
        # Verify the candidate record in _audit_records has correct attributions
        from redaction.escalation_manager import _audit_records
        key = ("Managing Innovation", "Managing Innovation")
        self.assertIn(key, _audit_records)
        record = _audit_records[key]
        self.assertEqual(record["escalation_reason"], "CLASSIFIER_CONFLICT")
        self.assertEqual(record["classifier_1"], "PERSON")
        self.assertEqual(record["classifier_2"], "ACADEMIC_TITLE")

if __name__ == '__main__':
    unittest.main()
