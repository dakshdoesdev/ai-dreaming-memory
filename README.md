# Dreaming Memory Research Lab

An arXiv research agent powered by **DeepSeek through AMD Token Lab**, with persistent SQLite memory and a repeatable comparison against ordinary lexical RAG.

The experiment asks whether compressed memories and synthetic replay improve paper recall and research-brief completion under a fixed context budget. Improvement is a hypothesis, not an assumption. Task success is a textual constraint proxy, not autonomous scientific discovery.

## What it does

1. Collects version-pinned arXiv metadata and full text, with local caching and content hashes.
2. Extracts methods, findings and author-reported research gaps using DeepSeek. Evidence segments are reconstructed from original text; model interpretations still require review.
3. Stores original chunks, compact memories and generated replay pairs persistently in SQLite.
4. Compares raw RAG, RAG plus memory, and RAG plus memory/replay on held-out questions.
5. Exports metrics, model answers, provenance hashes and limitations without publishing the downloaded papers.

Python 3.11+ and SQLite FTS5 are sufficient. There are **no external Python packages**. Poppler's `pdftotext` is needed only when an arXiv paper has no usable HTML.

## Setup

```bash
python3 -m unittest discover -v
python3 research_lab.py collect
python3 research_lab.py list
```

The default corpus is four pinned papers: CoALA (`2309.02427v3`), MemGPT (`2310.08560v2`), LongMemEval (`2410.10813v2`) and MemoryAgentBench (`2507.05257v4`). Full text and metadata stay in `data/papers.sqlite3` and `data/arxiv-cache/`; both are ignored by Git. Collection uses the arXiv Atom API, an abstract-page metadata fallback, and HTML/PDF text extraction with paced requests. Existing pinned text is never silently replaced.

Create your Token Lab key, then enter it without putting it in shell history:

```bash
read -rsp 'AMD Token Lab key: ' OPENAI_API_KEY; echo
export OPENAI_API_KEY
export OPENAI_BASE_URL=https://api.tokenlab.amd.com/v1
export TOKEN_LAB_MODEL=DeepSeek-V4-Flash
```

The callable model ID above was verified with Token Lab's authenticated `/models` endpoint. Catalog display names can differ from API IDs. Choose a chat model; Clef and d3 use a different endpoint. No key is included in this repository. Calls send selected paper text to AMD Token Lab and consume your account's points.

## Run the research pipeline

```bash
# Small, explicitly scoped initial study: first six chunks per paper.
python3 research_lab.py extract --max-chunks-per-paper 6 > data/extraction.json
python3 research_lab.py evaluate --max-chunks-per-paper 6 --out results/papers-pilot.json
python3 research_lab.py report results/papers-pilot.json --out results/papers-pilot.md

# Public export removes original retrieved passages and retains their hashes.
python3 research_lab.py export results/papers-pilot.json --out artifacts/papers-pilot.json
```

Prefix runs are labeled as such. The full paper texts remain stored, but a six-chunk pilot does **not** mean the full papers were analyzed. Extraction checkpoints identify complete/partial status; a failed chunk preserves earlier validated work. Re-running the same extraction resumes without paying for cached chunks. `--max-chunks` additionally limits new extraction calls globally.

For a full-corpus study, omit `--max-chunks-per-paper` from extraction and evaluation. This takes substantially more model calls. To consolidate the persistent corpus and ask questions:

```bash
python3 research_lab.py consolidate
python3 research_lab.py ask 'What are the LongMemEval memory design stages?' --arm rag
python3 research_lab.py ask 'What are the LongMemEval memory design stages?' --arm replay
```

Consolidation processes pending chunks in batches. Evaluation additionally runs consolidation after each six ingested chunks in a fresh temporary database. No background service is installed. Original paper text remains available even after compression. Extracted claims are stored separately and are not automatically promoted into factual retrieval.

## Evaluation

| Arm | Eligible evidence |
| --- | --- |
| `rag` | Original paper chunks |
| `summary` | Original chunks + compact memories |
| `replay` | Original chunks + compact memories + synthetic question/answer pairs |

The same model, answer prompt, BM25 implementation, retrieval count and serialized evidence character budget apply across arms. BM25 statistics are calculated separately on each eligible corpus. Arm order is seeded and shuffled. Each trial uses an isolated frozen corpus; evaluation answers are never written back into memory. Questions and expected answers are excluded from extraction and dreaming prompts.

`examples/paper_questions.json` contains a fixed 12-question rubric: factual recall, constrained research briefs, cross-paper comparison and abstention. Required answer groups accept listed aliases; all groups must match. This is transparent but imperfect: negations and paraphrases need manual auditing. The original conversation pilot remains available in `examples/pilot.json`.

Reports include per-category answer scores, supporting-paper recall, paired differences, raw model answers, retrieved provenance, token usage, latency, preprocessing costs, corpus/question hashes and corpus scope. Supporting-paper recall does not prove that the retrieved passage contains the answer. Confidence intervals are suppressed when there are too few support clusters. Repeated calls on the same papers do not create independent data.

```bash
python3 research_lab.py evaluate --repeats 3 --budget 1200 --max-chunks-per-paper 6 --out results/repeated.json
```

Output paths are reserved before inference; existing reports are never overwritten. A failed or interrupted evaluation leaves a `status: running` placeholder, which report/export commands reject. Successful-call usage is recorded; failed-request charges may be missing. Requests are paced below the supplied 20 RPM account limit, with bounded retries for 429 and selected 5xx errors. Run one model process per key at a time.

## Offline verification

```bash
python3 memory_lab.py --offline evaluate --out results/conversation-smoke.json
python3 research_lab.py --offline evaluate --max-chunks-per-paper 6 --out results/paper-smoke.json
```

Offline mode is a deliberately unintelligent test double that answers `UNKNOWN`. Its scores verify orchestration, not model capability. Offline extraction generates no fake scientific claims. The paper smoke test needs a collected corpus; unit tests need neither internet nor API credentials.

## Results and limitations

See [the published experiment report](artifacts/RESULTS.md) and [source research notes](docs/RESEARCH.md). Downloaded papers, databases, caches, keys and private run logs are excluded from publication. Public JSON replaces source passages with hashes; collect the pinned corpus to reproduce retrieval.

The initial live pilot passed **5/12 automatic rubric checks with raw RAG and 10/12 with either memory arm**. Replay added no accuracy gain. These are small, literal-rubric results; the report documents false negatives, higher token usage, preprocessing costs and extraction errors. They do not establish broad superiority.

This is a small custom paper-QA experiment, **not an official MemoryAgentBench result**. The initial study uses a limited prefix of four publicly known papers; models may have seen these papers in pretraining. Character budgets are not exact token budgets. Summary/replay generation costs are shared and reported separately; their construction costs are not independently isolated. Replay is retrieved data, not model fine-tuning. Claims of broad superiority require larger independent paper sets, expert-audited tasks, additional budgets and stronger retrieval baselines.

The MIT license covers this project's original code/documentation. Papers and third-party datasets retain their own licenses. Background and methodology draw on [MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench), [LongMemEval](https://github.com/xiaowu0162/LongMemEval), [MemGPT](https://arxiv.org/abs/2310.08560v2) and [CoALA](https://arxiv.org/abs/2309.02427v3).

## Original conversation agent

`memory_lab.py` also supports persistent conversation memory:

```bash
python3 memory_lab.py chat
python3 memory_lab.py add 'The Cedar project budget is 600 dollars.'
python3 memory_lab.py dream
python3 memory_lab.py ask 'What is the Cedar budget?' --arm replay
```

Chat consolidates every six user messages; `/dream` processes pending messages and `/quit` exits. Assistant replies are retained in transcripts but excluded from factual evidence. Different sessions in one database share memory; use separate `--db` paths for separate users/projects. SQLite storage is local plaintext.
