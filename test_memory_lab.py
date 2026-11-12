import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

import memory_lab as lab


class FixedDream:
    def __init__(self, memories):
        self.memories = memories

    def complete(self, system, prompt):
        return json.dumps({"memories": self.memories})


def fact(source_id=1, **changes):
    value = {"source_id": source_id, "text": "Tea preference",
             "evidence": "I prefer green tea in the morning.",
             "question": "What tea do I prefer?", "answer": "green tea"}
    value.update(changes)
    return value


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="memory-lab-test-")
        self.path = str(Path(self.tmp.name) / "memory.db")
        self.store = lab.Memory(self.path)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.store.close)

    def add_preference(self):
        return self.store.add("session", "user", "I prefer green tea in the morning.")

    def test_transcript_persists_but_assistant_is_not_evidence(self):
        self.add_preference()
        self.store.add("session", "assistant", "Invented coffee preference")
        with contextlib.closing(lab.Memory(self.path)) as reopened:
            self.assertEqual(reopened.db.execute("SELECT count(*) FROM messages").fetchone()[0], 2)
            self.assertEqual(reopened.pending(), 1)
            self.assertEqual(reopened.retrieve("coffee"), [])
            self.assertEqual(reopened.retrieve("green tea")[0]["sources"], [1])

    def test_dream_adds_summary_replay_once_and_preserves_baseline(self):
        self.add_preference()
        baseline = self.store.retrieve("tea", "rag")
        self.assertEqual(self.store.dream(FixedDream([fact()])), 1)
        self.assertEqual(self.store.pending(), 0)
        self.assertEqual(self.store.dream(FixedDream([fact()])), 0)
        self.assertEqual(self.store.retrieve("tea", "rag"), baseline)
        self.assertEqual({row["kind"] for row in self.store.retrieve("tea", "summary")}, {"raw", "summary"})
        self.assertEqual({row["kind"] for row in self.store.retrieve("tea", "replay")}, {"raw", "summary", "replay"})

    def test_ungrounded_dream_is_atomic(self):
        self.add_preference()
        for invalid in (fact(evidence="I prefer coffee"), fact(answer="coffee"),
                        fact(source_id=2), fact(source_id=True), fact(text="")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.store.dream(FixedDream([fact(), invalid]))
            self.assertEqual(self.store.pending(), 1)
            self.assertEqual(self.store.db.execute("SELECT count(*) FROM documents").fetchone()[0], 1)

    def test_uncompressed_dream_is_not_saved(self):
        self.add_preference()
        with self.assertRaisesRegex(ValueError, "compress"):
            self.store.dream(FixedDream([fact(text="I prefer green tea in the morning.")]))
        self.assertEqual(self.store.pending(), 1)

    def test_dream_limits_memories_per_source(self):
        self.add_preference()
        self.store.add("session", "user", "A second separate source message.")
        with self.assertRaisesRegex(ValueError, "two memories"):
            self.store.dream(FixedDream([fact(), fact(), fact()]))
        self.assertEqual(self.store.pending(), 2)

    def test_segment_dream_reconstructs_exact_replay_answer(self):
        source = "a" * 200 + "The tea is green. " * 12 + "z" * 100
        self.store.add("session", "user", source)
        model = Mock()
        model.complete.return_value = json.dumps({"memories": [{
            "source_id": 1, "text": "Green tea", "question": "What tea?", "evidence_segments": [1, 2]}]})
        self.assertEqual(self.store.dream(model), 1)
        sent = json.loads(model.complete.call_args.args[1])
        self.assertEqual(sent[0]["source_segments"][1], {"id": 1, "text": source[200:400]})
        replay = self.store.db.execute("SELECT text FROM documents WHERE kind='replay'").fetchone()[0]
        self.assertEqual(replay, "Q: What tea?\nA: " + source[200:600])

    def test_invalid_segment_dreams_never_change_memory(self):
        self.store.add("session", "user", "a" * 700)
        for source_id, selected in ((1, []), (1, [True]), (1, [-1]), (1, [4]),
                                     (1, [0, 1, 2, 3, 0]), (True, [0]), (2, [0])):
            model = Mock()
            model.complete.return_value = json.dumps({"memories": [{
                "source_id": source_id, "text": "Small fact", "question": "What?",
                "evidence_segments": selected}]})
            with self.subTest(source_id=source_id, selected=selected), self.assertRaises(ValueError):
                self.store.dream(model)
            self.assertEqual(model.complete.call_count, 2)
            self.assertEqual(self.store.pending(), 1)
            self.assertEqual(self.store.db.execute("SELECT count(*) FROM documents").fetchone()[0], 1)

    def test_nonconsecutive_segment_selection_uses_exact_covering_span(self):
        source = "a" * 200 + "b" * 200 + "c" * 200 + "d" * 100
        for selected in ([0, 2], [2, 0], [2, 0, 2]):
            with self.subTest(selected=selected):
                memories = lab._dream_memories(json.dumps({"memories": [{
                    "source_id": 1, "text": "Short fact", "question": "What?",
                    "evidence_segments": selected}]}), {1: source})
                self.assertEqual(memories[0]["answer"], source[:600])
                self.assertEqual(memories[0]["evidence"], source[:600])

    def test_covering_segment_span_retains_answer_size_limit(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            lab._dream_memories(json.dumps({"memories": [{
                "source_id": 1, "text": "Short fact", "question": "What?",
                "evidence_segments": [0, 10]}]}), {1: "a" * 2200})

    def test_dream_retries_invalid_output_once(self):
        self.add_preference()
        model = Mock()
        model.complete.side_effect = ["not JSON", json.dumps({"memories": [{
            "source_id": 1, "text": "Tea preference", "question": "What tea?", "evidence_segments": [0]}]})]
        self.assertEqual(self.store.dream(model), 1)
        self.assertEqual(model.complete.call_count, 2)
        self.assertIn("failed validation", model.complete.call_args.args[0])

    def test_malformed_dream_shape_is_a_value_error(self):
        self.add_preference()
        for output in ("[]", "{}", '{"memories":null}', '{"memories":[null]}', None):
            model = Mock()
            model.complete.return_value = output
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.store.dream(model)
            self.assertEqual(model.complete.call_count, 2)
            self.assertEqual(self.store.pending(), 1)

    def test_context_budget_and_k_never_truncate_evidence(self):
        self.add_preference()
        self.store.add("session", "user", "Tea is served at noon.")
        rows = self.store.retrieve("tea", k=1)
        self.assertEqual(len(rows), 1)
        exact_size = len(json.dumps(rows[0], ensure_ascii=False))
        self.assertEqual(len(self.store.retrieve("tea", k=1, budget=exact_size)), 1)
        self.assertEqual(self.store.retrieve("tea", budget=1), [])
        for row in self.store.retrieve("tea", budget=200):
            self.assertIn(row["text"], ("I prefer green tea in the morning.", "Tea is served at noon."))
        self.assertLessEqual(sum(len(json.dumps(row, ensure_ascii=False)) for row in self.store.retrieve("tea", budget=200)), 200)

    def test_invalid_input_and_query_punctuation(self):
        for role, text in (("system", "hello"), ("user", "  "), ("user", None)):
            with self.subTest(role=role, text=text), self.assertRaises(ValueError):
                self.store.add("session", role, text)
        self.add_preference()
        self.assertEqual(self.store.retrieve('" OR *'), [])
        self.assertEqual(self.store.retrieve("?!"), [])
        with self.assertRaises(ValueError):
            self.store.retrieve("tea", arm="missing")


class EvaluationTests(unittest.TestCase):
    def test_existing_report_rejected_before_benchmark(self):
        with tempfile.TemporaryDirectory(prefix="memory-lab-output-") as tmp:
            target = Path(tmp) / "existing.json"
            target.write_text('{"keep":true}')
            dataset = Path(tmp) / "dataset.json"
            dataset.write_text(json.dumps(self.dataset()))
            with patch.object(sys, "argv", ["memory_lab.py", "--offline", "evaluate", "--dataset", str(dataset), "--out", str(target)]), patch.object(lab, "benchmark") as run:
                with self.assertRaises(FileExistsError):
                    lab.main()
                run.assert_not_called()
            self.assertEqual(target.read_text(), '{"keep":true}')

    def test_chat_persists_input_when_model_fails(self):
        with tempfile.TemporaryDirectory(prefix="memory-lab-chat-") as tmp:
            path = str(Path(tmp) / "memory.db")
            with patch.object(sys, "argv", ["memory_lab.py", "--offline", "--db", path, "chat"]), patch("builtins.input", return_value="My favourite colour is blue."), patch.object(lab.SmokeModel, "complete", side_effect=ValueError("API unavailable")), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    lab.main()
            with contextlib.closing(lab.Memory(path)) as store:
                self.assertEqual(store.pending(), 1)
                self.assertEqual(store.db.execute("SELECT text FROM messages").fetchone()[0], "My favourite colour is blue.")

    def dataset(self):
        return [{"id": "episode", "history": ["I prefer green tea in the morning."], "questions": [
            {"kind": "recall", "question": "HELD_OUT_QUESTION tea?", "support": [1], "required": [["green tea"]]},
            {"kind": "abstention", "question": "UNSEEN birthday?", "support": [], "required": [["UNKNOWN"]]}]}]

    def test_rubric_aliases_boundaries_and_forbidden_terms(self):
        question = {"required": [["green tea", "matcha"], ["Monday"]], "forbidden": ["coffee"]}
        self.assertTrue(lab.grade("Matcha, on MONDAY.", question))
        self.assertFalse(lab.grade("Matcha on Monday with coffee", question))
        self.assertFalse(lab.grade("Matcha on Mondays", question))
        self.assertFalse(lab.grade("Green tea", question))
        self.assertTrue(lab.grade("UNKNOWN", {"kind": "abstention"}))
        self.assertFalse(lab.grade("UNKNOWN but the score is 90", {"kind": "abstention"}))

    def test_invalid_support_is_rejected_before_model_call(self):
        data = self.dataset()
        data[0]["questions"][0]["support"] = [2]
        with self.assertRaises(ValueError):
            lab.benchmark(lab.SmokeModel(), data)

    def test_benchmark_keeps_held_out_questions_and_answers_out_of_memory(self):
        class RecordingModel(lab.SmokeModel):
            prompts = []

            def complete(self, system, prompt):
                self.prompts.append((system, prompt))
                return super().complete(system, prompt)

        model = RecordingModel()
        report = lab.benchmark(model, self.dataset(), repeats=2)
        self.assertTrue(report["smoke_only"])
        self.assertEqual(len(report["records"]), 12)
        self.assertEqual(len(report["preprocessing"]), 2)
        for system, prompt in model.prompts:
            if system.startswith("Consolidate"):
                self.assertNotIn("HELD_OUT_QUESTION", prompt)
                self.assertNotIn("UNSEEN", prompt)
                self.assertNotIn("UNKNOWN", prompt)
            else:
                evidence = json.loads(prompt)["evidence"]
                self.assertNotIn("HELD_OUT_QUESTION", json.dumps(evidence))
                self.assertNotIn("UNSEEN", json.dumps(evidence))
                self.assertNotIn("UNKNOWN", json.dumps(evidence))
        self.assertEqual(set(report["metrics"]), set(lab.ARMS))
        self.assertEqual(report["metrics"]["rag"]["recall"], 0)
        self.assertEqual(report["metrics"]["rag"]["abstention"], 1)
        self.assertIsNone(report["metrics"]["rag"]["task"])

    def test_cli_periodic_dream_after_threshold(self):
        with tempfile.TemporaryDirectory(prefix="memory-lab-cli-") as tmp:
            path = str(Path(tmp) / "memory.db")
            command = [sys.executable, str(Path(lab.__file__)), "--offline", "--db", path, "add"]
            first = subprocess.run(command + ["I prefer green tea.", "--dream-every", "2"], text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            with contextlib.closing(lab.Memory(path)) as store:
                self.assertEqual(store.pending(), 1)
            second = subprocess.run(command + ["My lunch is at noon.", "--dream-every", "2"], text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("Consolidated messages: 2", second.stdout)
            with contextlib.closing(lab.Memory(path)) as store:
                self.assertEqual(store.pending(), 0)


class TokenLabTests(unittest.TestCase):
    def client(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret", "OPENAI_BASE_URL": "https://api.tokenlab.amd.com/v1"}):
            return lab.TokenLab()

    def response(self, content="answer", finish_reason="stop"):
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
                                    "usage": {"prompt_tokens": 7, "completion_tokens": 2}}).encode())

    def test_key_and_https_are_required(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            lab.TokenLab()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret", "OPENAI_BASE_URL": "http://example.com"}), self.assertRaisesRegex(ValueError, "HTTPS"):
            lab.TokenLab()

    def test_request_has_auth_model_and_records_usage(self):
        client, opener = self.client(), Mock()
        opener.open.return_value = self.response()
        with patch.object(lab.urllib.request, "build_opener", return_value=opener), patch.object(lab.time, "sleep"):
            self.assertEqual(client.complete("system", "prompt"), "answer")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.tokenlab.amd.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertFalse(json.loads(request.data)["stream"])
        self.assertEqual(client.calls[0]["usage"]["prompt_tokens"], 7)

    def test_structured_requests_enable_json_mode(self):
        client, opener = self.client(), Mock()
        opener.open.return_value = self.response('{"memories": []}')
        with patch.object(lab.urllib.request, "build_opener", return_value=opener), patch.object(lab.time, "sleep"):
            client.complete("Consolidate. Return ONLY JSON", "source")
        body = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_retry_after_and_nonretryable_auth_error(self):
        client, opener = self.client(), Mock()
        opener.open.side_effect = [urllib.error.HTTPError("url", 429, "rate", {"Retry-After": "9"}, None), self.response()]
        with patch.object(lab.urllib.request, "build_opener", return_value=opener), patch.object(lab.time, "sleep") as sleep:
            self.assertEqual(client.complete("system", "prompt"), "answer")
        self.assertIn(unittest.mock.call(9.0), sleep.call_args_list)
        opener.open.reset_mock()
        opener.open.side_effect = urllib.error.HTTPError("url", 401, "test-secret", {}, None)
        with patch.object(lab.urllib.request, "build_opener", return_value=opener), patch.object(lab.time, "sleep"), self.assertRaisesRegex(ValueError, "HTTP 401") as result:
            client.complete("system", "prompt")
        self.assertNotIn("test-secret", str(result.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_truncated_response_and_redirect_are_rejected(self):
        client, opener = self.client(), Mock()
        opener.open.return_value = self.response(finish_reason="length")
        with patch.object(lab.urllib.request, "build_opener", return_value=opener), patch.object(lab.time, "sleep"), self.assertRaisesRegex(ValueError, "truncated"):
            client.complete("system", "prompt")
        self.assertEqual(client.calls, [])
        self.assertIsNone(lab.NoRedirect().redirect_request(None, None, 302, None, {}, "https://elsewhere.test"))


if __name__ == "__main__":
    unittest.main()
