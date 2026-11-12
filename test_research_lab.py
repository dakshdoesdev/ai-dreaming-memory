import hashlib
import unittest

from research_lab import public_report, report_markdown


class ReportTests(unittest.TestCase):
    def test_unfinished_or_empty_reports_are_not_scientific_results(self):
        for value in ({"status": "running", "smoke_only": False}, {}):
            with self.assertRaises(ValueError):
                report_markdown(value)

    def test_public_report_redacts_source_passages_but_keeps_answers(self):
        original = {"records": [{"answer": "indexing, retrieval, reading", "evidence": [
            {"text": "A source passage", "sources": [3], "kind": "raw"}]}]}
        safe = public_report(original)
        entry = safe["records"][0]["evidence"][0]
        self.assertNotIn("text", entry)
        self.assertEqual(entry["text_sha256"], hashlib.sha256(b"A source passage").hexdigest())
        self.assertEqual(entry["sources"], [3])
        self.assertEqual(safe["records"][0]["answer"], original["records"][0]["answer"])
        self.assertIn("text", original["records"][0]["evidence"][0])

    def test_markdown_reports_scope_cost_and_limitations(self):
        rendered = report_markdown({"model": "test", "smoke_only": True,
            "metrics": {}, "records": [], "corpus_scope": "first_chunks_per_paper",
            "preprocessing_usage": {"requests": 4}, "limitations": ["Small sample"]})
        self.assertIn("OFFLINE SMOKE", rendered)
        self.assertIn("first_chunks_per_paper", rendered)
        self.assertIn('"requests": 4', rendered)
        self.assertIn("Small sample", rendered)


if __name__ == "__main__":
    unittest.main()
