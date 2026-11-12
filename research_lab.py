"""Collect arXiv papers, extract evidence, and compare memory against RAG."""

import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import time

from memory_lab import ARMS, SmokeModel, TokenLab, positive


DEFAULT_PAPERS = ["2410.10813v2", "2507.05257v4", "2310.08560v2", "2309.02427v3"]


def model_for(args):
    return SmokeModel() if args.offline else TokenLab()


def public_report(report):
    """Keep model answers/metrics, replace original retrieved passages with provenance hashes."""
    if isinstance(report, list):
        return [public_report(item) for item in report]
    if isinstance(report, dict):
        result = {}
        for key, value in report.items():
            if key in ("text", "evidence") and isinstance(value, str):
                result[key + "_sha256"] = hashlib.sha256(value.encode()).hexdigest()
                result[key + "_characters"] = len(value)
            else:
                result[key] = public_report(value)
        return result
    return report


def report_markdown(report):
    if report.get("status") == "running" or not all(key in report for key in ("metrics", "records", "model", "smoke_only")):
        raise ValueError("Only a completed experiment report can be rendered.")
    lines = ["# Paper memory experiment results", "",
             "**OFFLINE SMOKE TEST — not evidence of model capability.**" if report.get("smoke_only")
             else "Model-backed experimental run. Review raw answers and evidence before interpreting scores.", "",
             f"Model: `{report.get('model', 'unknown')}`", "",
             f"Corpus scope: `{report.get('corpus_scope', 'full')}`", "",
             "```json", json.dumps(report.get("metrics", {}), indent=2), "```", "",
             "## Paired differences and preprocessing cost", "", "```json",
             json.dumps({"paired_vs_rag": report.get("paired_vs_rag"),
                         "preprocessing_usage": report.get("preprocessing_usage"),
                         "papers": report.get("papers"),
                         "corpus_sha256": report.get("corpus_sha256"),
                         "questions_sha256": report.get("questions_sha256")}, indent=2), "```", "",
             "## Limitations", "",
             "This pilot uses lexical BM25 retrieval and textual constraint scoring. It does not execute "
             "real-world research tasks or fine-tune model weights. Paper evidence may be incomplete or "
             "extracted incorrectly. Compression and replay may reduce accuracy. A small hand-curated "
             "question set does not establish a general advantage over RAG.", "",
             "No claim is made that this is an official MemoryAgentBench run."]
    lines.extend(["", *["- " + note for note in report.get("limitations", [])]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/papers.sqlite3")
    parser.add_argument("--offline", action="store_true", help="Plumbing checks only; no model inference")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="Fetch full paper text and metadata from arXiv")
    collect.add_argument("ids", nargs="*", default=DEFAULT_PAPERS)
    collect.add_argument("--cache", default="data/arxiv-cache")
    sub.add_parser("list", help="List locally collected paper metadata")
    extract = sub.add_parser("extract", help="Extract methods/findings/author-reported gaps")
    extract.add_argument("--max-chunks", type=positive, default=None)
    extract.add_argument("--max-chunks-per-paper", type=positive, default=None,
                         help="Explicit prefix extraction pilot; default processes every chunk")
    consolidate = sub.add_parser("consolidate", help="Generate persistent compact memories and replay")
    consolidate.add_argument("--batch-size", type=positive, default=6)
    ask = sub.add_parser("ask", help="Ask a question using the selected retrieval arm")
    ask.add_argument("question")
    ask.add_argument("--arm", choices=ARMS, default="replay")
    evaluate = sub.add_parser("evaluate", help="Run held-out questions against isolated frozen corpus copies")
    evaluate.add_argument("--questions", default="examples/paper_questions.json")
    evaluate.add_argument("--repeats", type=positive, default=1)
    evaluate.add_argument("--seed", type=int, default=42)
    evaluate.add_argument("--k", type=positive, default=4)
    evaluate.add_argument("--budget", type=positive, default=2400)
    evaluate.add_argument("--max-chunks-per-paper", type=positive, default=None,
                          help="Explicit first-N-chunks pilot; default evaluates full corpus")
    evaluate.add_argument("--out", default=None)
    report = sub.add_parser("report", help="Render a saved experiment as a readable Markdown report")
    report.add_argument("input")
    report.add_argument("--out", required=True)
    export = sub.add_parser("export", help="Create a public JSON report without original source passages")
    export.add_argument("input")
    export.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command in ("report", "export"):
        saved = json.loads(Path(args.input).read_text())
        if saved.get("status") == "running":
            raise ValueError("An unfinished run cannot be exported.")
        if args.command == "report":
            content = report_markdown(saved)
        else:
            saved = public_report(saved)
            saved["source_passages_redacted"] = True
            content = json.dumps(saved, indent=2, ensure_ascii=False) + "\n"
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as handle:
            handle.write(content)
        print(target)
        return
    from paper_store import PaperStore, collect as collect_papers
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(PaperStore(args.db)) as store:
        if args.command == "collect":
            metadata = collect_papers(store, args.ids or DEFAULT_PAPERS, args.cache)
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps([paper["metadata"] for paper in store.get_papers()], indent=2, ensure_ascii=False))
        elif args.command == "extract":
            from paper_extract import extract_papers
            print(json.dumps(extract_papers(store, model_for(args), args.max_chunks,
                                           args.max_chunks_per_paper), indent=2))
        elif args.command == "consolidate":
            model = model_for(args)
            while store.memory.pending():
                print("Consolidated chunks:", store.memory.dream(model, args.batch_size))
        elif args.command == "ask":
            answer, evidence = store.memory.answer(model_for(args), args.question, args.arm)
            mapping = {row["message_id"]: row["arxiv_id"] for row in store.db.execute("SELECT message_id,arxiv_id FROM paper_chunks")}
            for entry in evidence:
                entry["paper_ids"] = sorted({mapping[sid] for sid in entry["sources"] if sid in mapping})
            print(json.dumps({"answer": answer, "evidence": evidence}, indent=2, ensure_ascii=False))
        else:
            from paper_eval import evaluate_papers
            questions = json.loads(Path(args.questions).read_text())
            target = Path(args.out or ("results/papers-" + time.strftime("%Y%m%d-%H%M%S") + ".json"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x") as handle:
                json.dump({"status": "running", "smoke_only": args.offline}, handle)
                handle.flush()
                report = evaluate_papers(store, model_for(args), questions, args.repeats, args.seed, args.k, args.budget,
                                         args.max_chunks_per_paper)
                handle.seek(0)
                handle.truncate()
                json.dump(report, handle, indent=2, ensure_ascii=False)
            print(json.dumps({"report": str(target), "metrics": report["metrics"], "smoke_only": report["smoke_only"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(str(error)) from None
