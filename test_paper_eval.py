import copy
import json
import unittest

from memory_lab import SmokeModel
from paper_eval import evaluate_papers


class FakeStore:
    def __init__(self):
        self.papers = [{"metadata": {"arxiv_id": "2507.05257v1", "title": "Memory test", "url": "https://arxiv.org/abs/2507.05257v1"},
            "text": " ".join(f"Chunk {index}: Paper memory uses retrieval and grounded evidence." for index in range(8)),
            "chunks": [{"message_id": 100 + index, "chunk_index": index,
                "text": f"Chunk {index}: Paper memory uses retrieval and grounded evidence."} for index in range(8)]}]

    def get_papers(self):
        return copy.deepcopy(self.papers)


class RecordingModel(SmokeModel):
    def __init__(self):
        super().__init__()
        self.prompts = []

    def complete(self, system, prompt):
        self.prompts.append((system, prompt))
        return super().complete(system, prompt)


class PaperEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.questions = [
            {"id": "recall", "question": "HELDOUT memory method?", "kind": "recall", "required": [["retrieval"]],
                "support_papers": ["2507.05257v1"]},
            {"id": "unknown", "question": "HELDOUT private password?", "kind": "abstention", "required": [["UNKNOWN"]],
                "support_papers": []}]

    def test_frozen_corpus_periodic_dream_and_no_heldout_leakage(self):
        before = copy.deepcopy(self.store.papers)
        model = RecordingModel()
        report = evaluate_papers(self.store, model, self.questions, repeats=2)
        self.assertEqual(self.store.papers, before)
        self.assertEqual(len(report["records"]), 12)
        self.assertTrue(report["smoke_only"])
        self.assertEqual([len(row["calls"]) for row in report["preprocessing"]], [2, 2])
        for system, prompt in model.prompts:
            if system.startswith("Consolidate"):
                self.assertNotIn("HELDOUT", prompt)
                self.assertNotIn("UNKNOWN", prompt)
            else:
                data = json.loads(prompt)
                self.assertNotIn("HELDOUT", json.dumps(data["evidence"]))
                self.assertNotIn("UNKNOWN", json.dumps(data["evidence"]))
        self.assertEqual(report["metrics"]["rag"]["recall"], 0)
        self.assertEqual(report["metrics"]["rag"]["abstention"], 1)
        self.assertIsNone(report["metrics"]["rag"]["task"])
        self.assertIsNone(report["paired_vs_rag"]["summary"]["bootstrap_95_ci"])

    def test_provenance_and_retrieval_budget(self):
        report = evaluate_papers(self.store, SmokeModel(), self.questions, k=1, budget=180)
        for record in report["records"]:
            self.assertLessEqual(len(record["evidence"]), 1)
            self.assertLessEqual(sum(len(json.dumps(row, ensure_ascii=False)) for row in record["evidence"]), 180)
            for value in record["source_provenance"].values():
                self.assertEqual(value["arxiv_id"], "2507.05257v1")
                self.assertIn(value["chunk_index"], range(8))

    def test_validation_precedes_paid_calls(self):
        for mutate in (lambda rows: rows[0].update(support_papers=["missing"]),
                       lambda rows: rows[0].update(required=[]),
                       lambda rows: rows[0].update(forbidden="bad"),
                       lambda rows: rows[1].update(id="recall"),
                       lambda rows: rows[1].update(support_papers=["2507.05257v1"])):
            questions = copy.deepcopy(self.questions)
            mutate(questions)
            model = RecordingModel()
            with self.subTest(questions=questions), self.assertRaises(ValueError):
                evaluate_papers(self.store, model, questions)
            self.assertEqual(model.calls, [])
        for kwargs in ({"repeats": 0}, {"k": True}, {"budget": -1}, {"max_chunks_per_paper": 0}):
            with self.assertRaises(ValueError):
                evaluate_papers(self.store, RecordingModel(), self.questions, **kwargs)

    def test_hashes_and_order_reproducible(self):
        first = evaluate_papers(self.store, SmokeModel(), self.questions)
        second = evaluate_papers(self.store, SmokeModel(), self.questions)
        self.assertEqual(first, second)
        self.store.papers[0]["chunks"][0]["text"] += " New evidence."
        changed = evaluate_papers(self.store, SmokeModel(), self.questions)
        self.assertNotEqual(first["corpus_sha256"], changed["corpus_sha256"])

    def test_prefix_scope_preserves_full_hash_and_excludes_later_chunks(self):
        model = RecordingModel()
        full = evaluate_papers(self.store, SmokeModel(), self.questions)
        report = evaluate_papers(self.store, model, self.questions, max_chunks_per_paper=2)
        self.assertEqual(report["corpus_scope"], "first_chunks_per_paper")
        self.assertEqual(report["original_chunk_count"], 8)
        self.assertEqual(report["evaluated_chunk_count"], 2)
        self.assertEqual(report["max_chunks_per_paper"], 2)
        self.assertEqual(report["papers"][0]["text_sha256"], full["papers"][0]["text_sha256"])
        self.assertNotEqual(report["papers"][0]["evaluated_chunks_sha256"], full["papers"][0]["evaluated_chunks_sha256"])
        self.assertFalse(report["question_source_coverage"]["answer_evidence_in_selected_chunks_verified"])
        for system, prompt in model.prompts:
            if system.startswith("Consolidate"):
                self.assertNotIn("Chunk 2:", prompt)
        self.assertEqual(report["report_version"], 1)

    def test_long_chunks_work_with_smoke_consolidation(self):
        self.store.papers[0]["chunks"][0]["text"] = "x" * 1600
        report = evaluate_papers(self.store, SmokeModel(), self.questions)
        self.assertTrue(report["smoke_only"])
        self.assertEqual(report["evaluated_chunk_count"], 8)

    def test_overlapping_paper_supports_share_one_cluster(self):
        self.store.papers.append({"metadata": {"arxiv_id": "2410.10813v1"}, "text": "Other memory paper evidence.",
            "chunks": [{"message_id": 999, "chunk_index": 0, "text": "Other memory paper evidence."}]})
        self.questions[0]["support_papers"].append("2410.10813v1")
        self.questions.append({"id": "second", "question": "Other method?", "kind": "task", "required": [["evidence"]],
            "support_papers": ["2410.10813v1"]})
        report = evaluate_papers(self.store, SmokeModel(), self.questions)
        self.assertEqual(report["paired_vs_rag"]["summary"]["support_clusters"], 2)
        self.assertEqual(report["metrics"]["replay"]["counts"], {"recall": 1, "task": 1, "abstention": 1})


if __name__ == "__main__":
    unittest.main()
