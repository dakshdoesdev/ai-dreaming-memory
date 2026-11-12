"""Repeatable, held-out paper-memory comparisons using the existing RAG engine."""

import contextlib
import hashlib
import json
from pathlib import Path
import random
import tempfile

from memory_lab import ARMS, Memory, SmokeModel, grade


def _positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer.")


def validate_questions(questions, paper_ids):
    """Validate the complete held-out rubric before any paid model request."""
    if not isinstance(questions, list) or not questions:
        raise ValueError("Questions must be a nonempty list.")
    seen = set()
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("Each question must be an object.")
        ident = question.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("Question IDs must be unique nonempty strings.")
        seen.add(ident)
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError("Questions need nonempty question text.")
        if question.get("kind") not in ("recall", "task", "abstention"):
            raise ValueError("Question kind must be recall, task or abstention.")
        groups = question.get("required")
        if not isinstance(groups, list) or not groups or not all(
                isinstance(group, list) and group and all(isinstance(alias, str) and alias.strip()
                for alias in group) for group in groups):
            raise ValueError("required must be nonempty groups of nonempty answer aliases.")
        forbidden = question.get("forbidden", [])
        if not isinstance(forbidden, list) or not all(isinstance(term, str) and term.strip() for term in forbidden):
            raise ValueError("forbidden must be a list of nonempty strings.")
        supports = question.get("support_papers")
        if (not isinstance(supports, list) or not all(isinstance(ident, str) and ident in paper_ids for ident in supports)
                or len(supports) != len(set(supports))):
            raise ValueError("support_papers must contain unique collected arXiv IDs.")
        if question["kind"] != "abstention" and not supports:
            raise ValueError("Recall/task questions need at least one supporting paper.")
        if question["kind"] == "abstention" and supports:
            raise ValueError("Abstention questions must have no supporting papers.")


def _usage(calls):
    totals = {"requests": len(calls), "seconds": sum(call.get("seconds", 0) for call in calls),
              "prompt_tokens": 0, "completion_tokens": 0, "requests_without_token_usage": 0}
    for call in calls:
        usage = call.get("usage", {})
        if not usage:
            totals["requests_without_token_usage"] += 1
        for field in ("prompt_tokens", "completion_tokens"):
            totals[field] += usage.get(field, 0) or 0
    return totals


def _question_clusters(questions):
    # Overlapping support sets belong to one cluster; repeats/questions are not independent samples.
    clusters = []
    for question in questions:
        supports = set(question["support_papers"]) or {"__abstention__"}
        overlapping = [cluster for cluster in clusters if cluster["papers"] & supports]
        merged = {"papers": set(supports), "questions": {question["id"]}}
        for cluster in overlapping:
            merged["papers"].update(cluster["papers"])
            merged["questions"].update(cluster["questions"])
            clusters.remove(cluster)
        clusters.append(merged)
    return clusters


def evaluate_papers(store, model, questions, repeats=1, seed=42, k=4, budget=2400,
                    max_chunks_per_paper=None):
    """Compare raw RAG, summaries and replay without changing the persistent store.

    PaperStore.get_papers() supplies metadata/text/chunks. The model implements
    complete(system, prompt), model and calls, as TokenLab and SmokeModel do.
    """
    for value, name in ((repeats, "repeats"), (k, "k"), (budget, "budget")):
        _positive(value, name)
    if max_chunks_per_paper is not None:
        _positive(max_chunks_per_paper, "max_chunks_per_paper")
    if type(seed) is not int:
        raise ValueError("seed must be an integer.")
    papers = store.get_papers()
    if not isinstance(papers, list) or not papers:
        raise ValueError("Collect at least one paper before evaluating.")
    frozen, manifest, paper_ids = [], [], set()
    for paper in papers:
        metadata = paper["metadata"]
        ident = metadata["arxiv_id"]
        if not isinstance(ident, str) or not ident or ident in paper_ids:
            raise ValueError("Collected paper IDs must be unique strings.")
        paper_ids.add(ident)
        original_chunks = sorted(paper["chunks"], key=lambda chunk: chunk["chunk_index"])
        if not original_chunks:
            raise ValueError(f"Paper {ident} has no text chunks.")
        chunks = original_chunks[:max_chunks_per_paper] if max_chunks_per_paper is not None else original_chunks
        for chunk in chunks:
            text = chunk["text"]
            if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                raise ValueError("Paper chunks must contain 1–2000 characters; rechunk before evaluating.")
            frozen.append({"paper_id": ident, "chunk_index": chunk["chunk_index"], "text": text})
        manifest.append({"arxiv_id": ident, "title": metadata.get("title"), "url": metadata.get("url"),
            "text_sha256": hashlib.sha256(paper["text"].encode()).hexdigest(), "chunks": len(chunks),
            "original_chunks": len(original_chunks), "evaluated_chunks": len(chunks),
            "evaluated_chunks_sha256": hashlib.sha256(json.dumps(
                [{"chunk_index": chunk["chunk_index"], "text": chunk["text"]} for chunk in chunks],
                sort_keys=True).encode()).hexdigest()})
    validate_questions(questions, paper_ids)
    rng, records, preprocessing, arm_orders = random.Random(seed), [], [], []
    for repeat in range(repeats):
        with tempfile.TemporaryDirectory(prefix="paper-eval-") as temp:
            with contextlib.closing(Memory(str(Path(temp) / "memory.sqlite3"))) as memory:
                sources = {}
                start = len(model.calls)
                for chunk in frozen:
                    source_id = memory.add(chunk["paper_id"], "user", chunk["text"])
                    sources[source_id] = {"arxiv_id": chunk["paper_id"], "chunk_index": chunk["chunk_index"]}
                    if memory.pending() >= 6:
                        memory.dream(model, batch_size=6)
                while memory.pending():
                    memory.dream(model, batch_size=6)
                calls = list(model.calls[start:])
                preprocessing.append({"repeat": repeat, "calls": calls, "usage": _usage(calls),
                    "storage_characters": {kind: memory.db.execute(
                        "SELECT coalesce(sum(length(text)),0) FROM documents WHERE kind=?", (kind,)).fetchone()[0]
                        for kind in ("raw", "summary", "replay")}})
                arms = list(ARMS)
                rng.shuffle(arms)
                arm_orders.append({"repeat": repeat, "arms": arms})
                for arm in arms:
                    for question in questions:
                        start = len(model.calls)
                        answer, evidence = memory.answer(model, question["question"], arm, k, budget)
                        source_ids = {source_id for entry in evidence for source_id in entry["sources"]}
                        found = {sources[source_id]["arxiv_id"] for source_id in source_ids}
                        required = set(question["support_papers"])
                        calls = list(model.calls[start:])
                        records.append({"question_id": question["id"], "repeat": repeat, "arm": arm,
                            "kind": question["kind"], "question": question["question"], "answer": answer,
                            "passed": grade(answer, question), "evidence": evidence,
                            "source_provenance": {str(ident): sources[ident] for ident in sorted(source_ids)},
                            "retrieved_papers": sorted(found), "support_papers": question["support_papers"],
                            "source_recall": len(found & required) / len(required) if required else None,
                            "calls": calls, "usage": _usage(calls)})
    metrics = {}
    for arm in ARMS:
        rows = [row for row in records if row["arm"] == arm]
        metrics[arm] = {"answer_accuracy": sum(row["passed"] for row in rows) / len(rows),
            "counts": {kind: sum(row["kind"] == kind for row in rows) for kind in ("recall", "task", "abstention")},
            "usage": _usage([call for row in rows for call in row["calls"]])}
        for kind in ("recall", "task", "abstention"):
            subset = [row for row in rows if row["kind"] == kind]
            metrics[arm][kind] = sum(row["passed"] for row in subset) / len(subset) if subset else None
        recalls = [row["source_recall"] for row in rows if row["source_recall"] is not None]
        metrics[arm]["source_recall"] = sum(recalls) / len(recalls) if recalls else None
    clusters, paired = _question_clusters(questions), {}
    for arm in ARMS[1:]:
        deltas = []
        for cluster in clusters:
            rates = {name: [row["passed"] for row in records if row["arm"] == name
                and row["question_id"] in cluster["questions"]] for name in ("rag", arm)}
            deltas.append(sum(rates[arm]) / len(rates[arm]) - sum(rates["rag"]) / len(rates["rag"]))
        interval = None
        if len(deltas) >= 5:
            samples = sorted(sum(rng.choices(deltas, k=len(deltas))) / len(deltas) for _ in range(2000))
            interval = [samples[49], samples[1949]]
        paired[arm] = {"mean_support_cluster_delta": sum(deltas) / len(deltas), "support_clusters": len(deltas),
            "bootstrap_95_ci": interval, "uncertainty": "Exploratory, conditional on one shared corpus; not independent corpus trials."
            if interval else "Too few support clusters (<5); no confidence interval reported."}
    return {"report_version": 1, "experiment": "paper-memory-pilot", "model": model.model,
        "smoke_only": isinstance(model, SmokeModel),
        "repeats": repeats, "seed": seed, "retrieval_k": k, "context_char_budget": budget,
        "corpus_scope": "first_chunks_per_paper" if max_chunks_per_paper is not None else "all_collected_chunks",
        "max_chunks_per_paper": max_chunks_per_paper,
        "original_chunk_count": sum(paper["original_chunks"] for paper in manifest),
        "evaluated_chunk_count": len(frozen),
        "question_source_coverage": {"granularity": "paper", "all_support_papers_present": True,
            "answer_evidence_in_selected_chunks_verified": False,
            "limitation": "Support labels identify papers, not answer-bearing chunks; a selected prefix may omit the required evidence."},
        "consolidation_every_chunks": 6, "arm_orders": arm_orders, "papers": manifest,
        "corpus_sha256": hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(),
        "questions_sha256": hashlib.sha256(json.dumps(questions, sort_keys=True).encode()).hexdigest(),
        "metrics": metrics, "paired_vs_rag": paired, "preprocessing": preprocessing, "records": records,
        "preprocessing_usage": _usage([call for entry in preprocessing for call in entry["calls"]]),
        "limitations": [
            "A custom paper QA pilot, not an official MemoryAgentBench run.",
            "Task completion is textual constraint satisfaction, not external tool execution.",
            "Alias matching can miss correct paraphrases or accept incorrect negated answers; audit raw answers.",
            "Supporting-paper provenance recall does not prove a chunk or summary contains the answer.",
            "Prefix pilots use the first N chunks without question-driven selection; answer-bearing evidence may lie outside that prefix."
            if max_chunks_per_paper is not None else "All collected chunks are evaluated, but answer-bearing evidence coverage is not manually verified.",
            "All papers share one corpus; support-cluster bootstrap intervals are exploratory, not population claims.",
            "Summary/replay preprocessing is generated together and shared; raw RAG needs none of that cost.",
            "Replay is retrieved synthetic text, not model training. Character budgets are not token budgets.",
            "API usage is provider-reported successful-call usage; failed-request charges may be missing.",
            "Temperature zero and repeated hosted calls do not guarantee deterministic outputs."]}
