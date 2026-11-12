import json
import sqlite3
import unittest

from memory_lab import SmokeModel
from paper_extract import extract_papers


class Store:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.papers = [{"metadata": {"arxiv_id": "2507.05257v1", "title": "Memory paper",
            "text_sha256": "a" * 64}, "text": "We use retrieval. Future work needs larger tests.",
            "chunks": [{"message_id": 1, "chunk_index": 0, "text": "We use retrieval."},
                       {"message_id": 2, "chunk_index": 1, "text": "Future work needs larger tests."}]}]

    def get_papers(self):
        return self.papers


class Model:
    model = "deepseek-test"

    def __init__(self):
        self.calls = []
        self.invalid = None

    def complete(self, system, prompt):
        data = json.loads(prompt)
        self.calls.append({"usage": {"prompt_tokens": 10, "completion_tokens": 5}, "seconds": 0})
        if self.invalid:
            return self.invalid
        return json.dumps({"claims": [{"kind": "method" if data["message_id"] == 1 else "gap",
            "text": "Retrieval" if data["message_id"] == 1 else "Larger tests needed",
            "evidence": data["excerpt"], "message_id": data["message_id"]}]})


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.store, self.model = Store(), Model()
        self.addCleanup(self.store.db.close)

    def checkpoint(self):
        return self.store.db.execute("SELECT claims,processed_sources,status FROM paper_extractions").fetchall()

    def test_all_chunks_grounded_and_cached(self):
        report = extract_papers(self.store, self.model)
        self.assertEqual(report["papers_complete"], 1)
        self.assertEqual(report["claims_total"], 2)
        self.assertEqual(report["usage"]["prompt_tokens"], 20)
        self.assertEqual(report["papers"][0]["claims"][1]["gap_origin"], "author_reported")
        again = extract_papers(self.store, self.model)
        self.assertEqual(again["chunks_processed"], 0)
        self.assertEqual(again["cached_chunks"], 2)
        self.assertEqual(len(self.model.calls), 2)

    def test_partial_resumes_without_reextracting_cached_chunk(self):
        first = extract_papers(self.store, self.model, max_chunks=1)
        self.assertEqual(first["papers_partial"], 1)
        self.assertEqual(first["papers_complete"], 0)
        second = extract_papers(self.store, self.model)
        self.assertEqual(second["papers_complete"], 1)
        self.assertEqual(second["chunks_processed"], 1)
        self.assertEqual(len(self.model.calls), 2)

    def test_invalid_json_preserves_prior_checkpoint(self):
        extract_papers(self.store, self.model, max_chunks=1)
        before = self.checkpoint()
        self.model.invalid = "not json"
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            extract_papers(self.store, self.model)
        self.assertEqual(self.checkpoint(), before)

    def test_ungrounded_quote_and_wrong_source_rejected(self):
        for changes in ({"evidence": "Unwritten claim"}, {"message_id": 2},
                        {"message_id": True}, {"kind": "inferred_gap"}, {"text": ""}):
            claim = {"kind": "method", "text": "Retrieval", "evidence": "We use retrieval.", "message_id": 1}
            claim.update(changes)
            self.model.invalid = json.dumps({"claims": [claim]})
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                extract_papers(self.store, self.model)
            self.assertEqual(self.checkpoint(), [])

    def test_error_on_second_chunk_preserves_first_then_resumes(self):
        original = self.model.complete
        def fail_second(system, prompt):
            return "bad" if json.loads(prompt)["message_id"] == 2 else original(system, prompt)
        self.model.complete = fail_second
        with self.assertRaises(ValueError):
            extract_papers(self.store, self.model)
        saved = self.checkpoint()
        self.assertEqual(len(saved), 1)
        self.assertEqual(json.loads(saved[0][1]), [1])
        self.assertEqual(saved[0][2], "partial")
        self.assertEqual(len(json.loads(saved[0][0])), 1)
        self.model.complete = original
        resumed = extract_papers(self.store, self.model)
        self.assertEqual(resumed["chunks_processed"], 1)
        self.assertEqual(resumed["cached_chunks"], 1)
        self.assertEqual(resumed["papers_complete"], 1)
        self.assertEqual(resumed["claims_total"], 2)

    def test_new_hash_or_model_does_not_reuse_old_claims(self):
        extract_papers(self.store, self.model)
        self.store.papers[0]["metadata"]["text_sha256"] = "b" * 64
        second = extract_papers(self.store, self.model)
        self.assertEqual(second["chunks_processed"], 2)
        self.model.model = "another-model"
        third = extract_papers(self.store, self.model)
        self.assertEqual(third["chunks_processed"], 2)
        self.assertEqual(len(self.checkpoint()), 3)

    def test_offline_does_not_invent_claims_or_mark_complete(self):
        model = SmokeModel()
        report = extract_papers(self.store, model)
        self.assertTrue(report["smoke_only"])
        self.assertEqual(report["claims_total"], 0)
        self.assertEqual(report["papers_complete"], 0)
        self.assertEqual(report["papers"][0]["status"], "smoke")
        self.assertEqual(model.calls, [])

    def test_limits_and_empty_paper_validation(self):
        for value in (0, -1, True, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                extract_papers(self.store, self.model, value)
        self.store.papers[0]["chunks"] = []
        with self.assertRaisesRegex(ValueError, "no indexed chunks"):
            extract_papers(self.store, self.model)

    def test_chunk_limit_is_global_across_papers(self):
        self.store.papers.append({"metadata": {"arxiv_id": "2410.10813v1", "title": "Second paper",
            "text_sha256": "c" * 64}, "text": "We use retrieval.",
            "chunks": [{"message_id": 3, "chunk_index": 0, "text": "We use retrieval."}]})
        result = extract_papers(self.store, self.model, max_chunks=1)
        self.assertEqual(result["chunks_processed"], 1)
        self.assertEqual(result["papers_partial"], 2)
        self.assertEqual(len(self.model.calls), 1)

    def test_malformed_claim_schema_rejected(self):
        for output in ('[]', '{"claims":{}}', '{"claims":[null]}', '{"other":[]}'):
            self.model.invalid = output
            with self.subTest(output=output), self.assertRaises(ValueError):
                extract_papers(self.store, self.model)
            self.assertEqual(self.checkpoint(), [])

    def test_segment_evidence_is_reconstructed_without_model_copying(self):
        source = "a" * 300 + "b" * 300 + "c" * 300 + "d" * 200
        self.store.papers[0]["chunks"] = [{"message_id": 1, "chunk_index": 0, "text": source}]
        def segment_model(system, prompt):
            data = json.loads(prompt)
            self.assertEqual("".join(segment["text"] for segment in data["source_segments"]), source)
            return json.dumps({"claims": [{"kind": "method", "text": "A method",
                "message_id": 1, "evidence_segments": [1, 2]}]})
        self.model.complete = segment_model
        result = extract_papers(self.store, self.model)
        self.assertEqual(result["papers"][0]["claims"][0]["evidence"], source[300:900])

    def test_invalid_segment_ids_rejected(self):
        self.store.papers[0]["chunks"][0]["text"] = "a" * 1200
        for selected in ([], [True], [-1], [4], [0, 1, 2, 3, 0], "0"):
            self.model.invalid = json.dumps({"claims": [{"kind": "method", "text": "A method",
                "message_id": 1, "evidence_segments": selected}]})
            with self.subTest(selected=selected), self.assertRaisesRegex(ValueError, "Evidence segments"):
                extract_papers(self.store, self.model)
            self.assertEqual(self.checkpoint(), [])

    def test_nonconsecutive_segments_use_exact_covering_span(self):
        source = "a" * 300 + "b" * 300 + "c" * 300 + "d" * 300
        self.store.papers[0]["chunks"][0]["text"] = source
        self.model.invalid = json.dumps({"claims": [{"kind": "method", "text": "A method",
            "evidence_segments": [2, 0]}]})
        result = extract_papers(self.store, self.model, max_chunks=1)
        self.assertEqual(result["papers"][0]["claims"][0]["evidence"], source[:900])

    def test_covering_span_larger_than_2000_is_rejected(self):
        self.store.papers[0]["chunks"][0]["text"] = "a" * 2400
        self.model.invalid = json.dumps({"claims": [{"kind": "method", "text": "A method",
            "evidence_segments": [0, 7]}]})
        with self.assertRaisesRegex(ValueError, "Ungrounded"):
            extract_papers(self.store, self.model)
        self.assertEqual(self.checkpoint(), [])

    def test_per_paper_prefix_is_partial_for_full_paper(self):
        self.store.papers.append({"metadata": {"arxiv_id": "2410.10813v1", "title": "Second paper",
            "text_sha256": "c" * 64}, "text": "Second paper text.",
            "chunks": [{"message_id": 3, "chunk_index": 0, "text": "First second-paper chunk."},
                       {"message_id": 4, "chunk_index": 1, "text": "Last second-paper chunk."}]})
        result = extract_papers(self.store, self.model, max_chunks_per_paper=1)
        self.assertEqual(result["chunks_processed"], 2)
        self.assertEqual(result["papers_complete"], 0)
        self.assertEqual(result["papers_partial"], 2)
        self.assertEqual(result["scope"]["mode"], "first_chunks")
        self.assertTrue(all(paper["requested_scope_complete"] for paper in result["papers"]))
        self.assertTrue(all(paper["total_chunks"] == 2 and paper["requested_chunks"] == 1 for paper in result["papers"]))
        again = extract_papers(self.store, self.model, max_chunks_per_paper=1)
        self.assertEqual(again["chunks_processed"], 0)
        full = extract_papers(self.store, self.model)
        self.assertEqual(full["chunks_processed"], 2)
        self.assertEqual(full["papers_complete"], 2)
        prefix_from_cache = extract_papers(self.store, self.model, max_chunks_per_paper=1)
        self.assertEqual(prefix_from_cache["claims_total"], 2)
        self.assertEqual(prefix_from_cache["papers_complete"], 2)
        self.assertEqual(prefix_from_cache["chunks_processed"], 0)

    def test_invalid_per_paper_limit_rejected(self):
        for value in (0, -1, True, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_chunks_per_paper"):
                extract_papers(self.store, self.model, max_chunks_per_paper=value)

    def test_invalid_first_response_retries_once_then_saves_valid_claim(self):
        self.store.papers[0]["chunks"] = [self.store.papers[0]["chunks"][0]]
        original = self.model.complete
        prompts = []
        def repair(system, prompt):
            prompts.append(json.loads(prompt))
            valid = original(system, prompt)
            return "invalid json" if len(prompts) == 1 else valid
        self.model.complete = repair
        result = extract_papers(self.store, self.model)
        self.assertEqual(len(prompts), 2)
        self.assertIn("validation_error", prompts[1])
        self.assertIn("covering", prompts[1]["correction"])
        self.assertEqual(result["papers_complete"], 1)
        self.assertEqual(result["claims_total"], 1)
        self.assertEqual(len(result["calls"]), 2)

    def test_invalid_output_has_exactly_two_attempts(self):
        self.model.invalid = "bad JSON"
        with self.assertRaises(ValueError):
            extract_papers(self.store, self.model)
        self.assertEqual(len(self.model.calls), 2)
        self.assertEqual(self.checkpoint(), [])

    def test_omitted_model_message_id_uses_canonical_source(self):
        self.model.invalid = json.dumps({"claims": [{"kind": "method", "text": "Retrieval",
            "evidence_segments": [0]}]})
        result = extract_papers(self.store, self.model, max_chunks=1)
        claim = result["papers"][0]["claims"][0]
        self.assertEqual(claim["message_id"], 1)
        self.assertEqual(claim["evidence"], self.store.papers[0]["chunks"][0]["text"])


if __name__ == "__main__":
    unittest.main()
