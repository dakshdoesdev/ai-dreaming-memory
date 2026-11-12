# CLI reference

Run commands from the repository root with Python 3.11+ and SQLite FTS5. The application uses Python's standard library. Poppler's `pdftotext` is needed only for the PDF fallback when a paper has no usable HTML.

There are two entry points:

- `research_lab.py`: collect and study papers.
- `memory_lab.py`: store conversations and run the synthetic conversation pilot.

Global options go **before** the command. Paths are relative to your current working directory.

## Model configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | None; required for live inference | AMD Token Lab key. Keep it out of source, reports and commits. |
| `OPENAI_BASE_URL` | `https://api.tokenlab.amd.com/v1` | HTTPS base URL for the compatible chat API. |
| `TOKEN_LAB_MODEL` | `DeepSeek-V4-Flash` | Callable model ID; the catalog display name may differ. |

The application does not load `.env` files. Set variables in the shell as shown in the [getting-started guide](../README.md#quick-start). Model calls send selected text to the configured service and consume the account's budget.

`--offline` substitutes an unintelligent test double for the model. Answers are always `UNKNOWN`; offline extraction produces no scientific claims. It does **not** disable the network collector: `research_lab.py --offline collect` still fetches arXiv papers.

## Paper research commands

```bash
python3 research_lab.py [--db PATH] [--offline] COMMAND
```

`--db` defaults to `data/papers.sqlite3`. `report` and `export` read saved files without opening a database or requiring a model key.

### Collect and inspect

```bash
python3 research_lab.py collect
python3 research_lab.py collect 2410.10813v2 2507.05257v4 --cache data/arxiv-cache
python3 research_lab.py list
```

`collect [ids ...]` accepts arXiv IDs or supported HTTPS arXiv paper URLs. With no IDs, it collects these pinned versions: `2410.10813v2`, `2507.05257v4`, `2310.08560v2`, `2309.02427v3`. Unversioned requests are pinned on collection. `--cache` defaults to `data/arxiv-cache`.

The collector stores full extracted text and metadata, then indexes chunks. It uses Atom metadata with an abstract-page fallback, followed by HTML text or PDF extraction. It refuses to substitute an abstract for missing full text. Repeating a collection reuses the cache and does not duplicate an unchanged paper. A different text hash for an already stored version is rejected; use a separate database to compare another extraction without replacing the old one.

`list` prints collected metadata as JSON. Collection and listing do not require a Token Lab key.

### Extract candidate claims

```bash
python3 research_lab.py extract --max-chunks-per-paper 6
python3 research_lab.py extract --max-chunks 8
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-chunks-per-paper N` | No limit | Process only the first N chunks of each paper. |
| `--max-chunks N` | No limit | Cap new chunk processing across all papers for this invocation. |

Both limits must be positive integers. Omitting them requests every collected chunk. The command prints JSON to stdout. If redirecting it to a file, remember that shell `>` overwrites that file; choose a fresh filename.

Checkpoints are keyed by paper ID, model ID and source-text hash. Validated chunks are committed individually; later failures preserve earlier work. Repeating the command resumes the matching checkpoint. Reports distinguish the requested prefix's completion from full-paper status: processing six chunks can complete the requested scope while the paper remains `partial`.

Claims are model interpretations labeled `method`, `finding` or `gap`. Evidence spans are reconstructed from the original source. This verifies provenance, not scientific truth or correct gap classification. Extracted claims remain separate from the retrieval index.

### Consolidate and ask

```bash
python3 research_lab.py consolidate --batch-size 6
python3 research_lab.py ask 'What are LongMemEval’s memory design stages?' --arm rag
python3 research_lab.py ask 'What are LongMemEval’s memory design stages?' --arm replay
```

`consolidate` processes all pending user-source chunks, in batches of six by default. Its batch size must be positive. A batch over 16,000 input characters is rejected; reduce the batch size or split a long source. There is no timer or background service.

`ask QUESTION` prints the answer and retrieved evidence as JSON, including source IDs and mapped paper IDs. It does not save the question or answer. `--arm` defaults to `replay`:

| Arm | Eligible retrieval documents |
| --- | --- |
| `rag` | Original user-source chunks |
| `summary` | Originals plus compressed memories |
| `replay` | Originals, compressed memories and synthetic Q&A |

Asking uses the engine defaults of at most four documents and a 2400-character evidence budget. The `ask` command does not expose flags for those limits.

### Evaluate a frozen corpus

```bash
python3 research_lab.py evaluate --max-chunks-per-paper 6 --out results/pilot.json
python3 research_lab.py --offline evaluate --max-chunks-per-paper 6 --out results/paper-smoke.json
```

The paper database must already contain a corpus, including for offline evaluation. Each repeat creates a fresh temporary memory database and leaves the persistent database unchanged. Consolidation runs after each six ingested chunks and flushes the remainder. All three arms use that frozen corpus; answers are not fed back into memory.

| Option | Default | Meaning |
| --- | --- | --- |
| `--questions PATH` | `examples/paper_questions.json` | Held-out question/rubric JSON. |
| `--repeats N` | `1` | Positive repeat count. |
| `--seed N` | `42` | Integer seed for arm ordering and bootstrap sampling. |
| `--k N` | `4` | Maximum retrieved documents per answer. |
| `--budget N` | `2400` | Budget for serialized evidence entries, in characters. |
| `--max-chunks-per-paper N` | No limit | First-N prefix pilot; otherwise use all collected chunks. |
| `--out PATH` | Timestamped JSON under `results/` | New report path; existing files are rejected. |

`k`, `budget` and the prefix limit must be positive. A character budget is not a token budget. A seed does not make hosted inference deterministic.

The question file is a JSON list. Each item needs a unique `id`, `question`, `kind` (`recall`, `task`, `abstention`), `required` alias groups, and `support_papers` containing collected versioned IDs. `forbidden` is optional. All required groups must match; any alias within a group is sufficient. Abstention requires normalized `UNKNOWN` and an empty support list. See [the fixed pilot questions](../examples/paper_questions.json) and [experiment protocol](EXPERIMENT.md).

Reports include scores, raw answers, retrieved evidence, usage, hashes, corpus scope and paired differences. Supporting-paper recall is not answer-citation correctness. Prefix selection does not automatically verify that every answer appears in the selected chunks. Confidence intervals are suppressed with fewer than five connected support clusters.

### Render and export reports

```bash
python3 research_lab.py report results/pilot.json --out results/pilot.md
python3 research_lab.py export results/pilot.json --out artifacts/pilot-public.json
```

`report INPUT --out PATH` renders a completed evaluation JSON as Markdown. `export INPUT --out PATH` accepts a completed evaluation or extraction report. Both create parent directories, reject existing output files, and reject an unfinished `status: running` report.

Export replaces source `text` and `evidence` strings with hashes and character counts; extracted interpretation text is retained under `interpretation`. Model answers are retained too, so inspect them before publication: redacting retrieval fields does not guarantee that answers contain no source quotations. Export does not upload anything to GitHub or check paper redistribution rights.

Evaluation reserves its output before inference. A failed or interrupted run can leave a `status: running` placeholder. Use a new output path for another run; that placeholder is not a completed scientific result.

## Conversation commands

```bash
python3 memory_lab.py [--db PATH] [--offline] COMMAND
```

The default database is `data/memory.sqlite3`.

| Command | Arguments and defaults | Behavior |
| --- | --- | --- |
| `add TEXT` | `--session default`, `--dream-every 6` | Save a user message; consolidate one threshold-sized batch when enough pending user messages exist. |
| `chat` | `--session default`, `--dream-every 6` | Interactive conversation; save turns and consolidate after the pending threshold. |
| `dream` | `--batch-size 6` | Process pending user messages until none remain. |
| `ask QUESTION` | `--arm replay` | Print an answer and evidence without saving the query. |
| `evaluate` | See below | Run isolated synthetic-history trials; does not use the conversation database. |

All threshold and batch values must be positive. `chat` accepts `/dream` to flush pending messages and `/quit` to exit. User input is stored before its API answer is requested, so a failed answer does not discard that input. Assistant replies are retained in the transcript but are excluded from factual retrieval and consolidation.

Sessions in one database share retrieval and pending-message counts; a session name is not a privacy boundary. Use separate `--db` paths for separate people or projects.

Conversation evaluation accepts `--dataset examples/pilot.json`, `--repeats 1`, `--seed 42`, `--k 4`, `--budget 2400` and optional `--out`. Without `--out`, it creates a timestamped JSON under `results/`. Its dataset uses independent `history`/`questions` episodes and 1-based message `support` indices, unlike the paper evaluator's `support_papers` IDs.

```bash
python3 memory_lab.py --offline evaluate --out results/conversation-smoke.json
```

## Common failures

| Symptom | Action |
| --- | --- |
| Missing `OPENAI_API_KEY` | Export the variable before live extraction, consolidation, asking or evaluation. Offline smoke mode needs no key. |
| Token Lab HTTP 401/403 or model error | Check the active key, callable model ID and account access. Do not put credentials in bug reports. |
| HTTP 429 or selected 5xx errors | The client makes at most three HTTP attempts, with bounded waits. Run one model process per key to avoid competing rate limits. |
| Invalid generated source IDs, schema or evidence | One structured-output correction retry is attempted. If it still fails, the current consolidation batch is unsaved; extraction retains prior validated chunk checkpoints. |
| Truncated/empty model output | Reduce the work requested; truncated text is not accepted as a valid record. |
| Existing output path | Choose a fresh path rather than expecting overwrite behavior. |
| No usable paper HTML and missing `pdftotext` | Provide Poppler for PDF extraction. Scanned PDFs requiring OCR are not supported. |
| SQLite reports missing FTS5 | Use a Python/SQLite build with FTS5 support. |

SQLite databases are local plaintext. Raw reports can contain original excerpts. The default `data/` and `results/` directories are ignored by Git; custom paths need the same care.
