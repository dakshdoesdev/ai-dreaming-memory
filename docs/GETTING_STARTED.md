# Run your first paper-memory experiment

This walkthrough is for Python developers who want to inspect the experiment locally, then optionally use AMD Token Lab. Run commands from the repository root. You need Python 3.11+ with SQLite FTS5; there is no runtime Python package installation step.

## 1. Check the local installation

```bash
python3 --version
python3 -c "import sqlite3; c = sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE f USING fts5(text)'); print('SQLite FTS5 available')"
python3 -m unittest discover -v
```

Tests use temporary databases and mocked network responses. They do not need internet or a model key.

Try the conversation experiment without a model:

```bash
python3 memory_lab.py --offline evaluate --out results/first-smoke.json
```

The smoke model answers `UNKNOWN`. A completed report proves that the workflow ran, not that memory improves recall. Existing output paths are rejected; choose a new name for another run.

## 2. Collect the versioned papers

```bash
python3 research_lab.py collect
python3 research_lab.py list
```

Collection needs internet but no Token Lab key. It fetches the four pinned papers listed in the [corpus manifest](../artifacts/corpus-manifest.json), caching source material in `data/arxiv-cache/` and storing text/chunks in `data/papers.sqlite3`. Files under `data/` are ignored by Git.

If HTML is unavailable, collection uses Poppler's `pdftotext`. Check `pdftotext -v` if that fallback fails. The collector does not silently replace full text with an abstract, and scanned PDFs requiring OCR are outside its scope. It paces requests and reuses cached downloads.

For a paper workflow smoke test after collection:

```bash
python3 research_lab.py --offline evaluate --max-chunks-per-paper 6 --out results/first-paper-smoke.json
```

`--offline` replaces model inference; it does not disable the arXiv collector's network access.

## 3. Configure AMD Token Lab

Create a key in your own Token Lab account. In Bash, enter it without putting it in history:

```bash
read -rsp 'AMD Token Lab key: ' OPENAI_API_KEY; echo
export OPENAI_API_KEY
export OPENAI_BASE_URL=https://api.tokenlab.amd.com/v1
export TOKEN_LAB_MODEL=DeepSeek-V4-Flash
```

No `.env` loader is provided. Use a callable chat-model ID from your account; Clef and d3 use a different endpoint. Live calls transmit selected paper text to AMD Token Lab and consume its points budget. Run one model process per key at a time to avoid combined rate-limit pressure.

## 4. Extract and compare a small prefix

```bash
python3 research_lab.py extract --max-chunks-per-paper 6 > data/first-extraction.json
python3 research_lab.py evaluate --max-chunks-per-paper 6 --out results/first-pilot.json
python3 research_lab.py report results/first-pilot.json --out results/first-pilot.md
```

Extraction generates candidate methods, findings and gaps. Validated chunks are checkpointed, so retrying the command resumes prior work. The first-six-chunks scope can be complete while the full-paper status remains `partial`. Scientific interpretations and gap classification still need review.

Evaluation builds an isolated frozen copy of the selected corpus and compares raw RAG, compact memory and memory plus replay. It does not modify the persistent collection database or learn from benchmark answers. Read the JSON answers and limitations rather than treating the headline score as proof of a general advantage.

Shell `>` overwrites an extraction output file, even though extraction checkpoints persist in SQLite. Choose fresh output filenames when you want to retain earlier reports. Evaluation, Markdown report and public-export destinations reject existing files. A failed evaluation leaves a `status: running` placeholder that cannot be rendered or exported as a completed result.

Omit `--max-chunks-per-paper` only when you intend a full-text run and its larger model-call budget. Prefix selection does not automatically prove every question's evidence is present; review new question sets against the selected scope.

## 5. Use persistent memory

```bash
python3 research_lab.py consolidate --batch-size 6
python3 research_lab.py ask 'What are LongMemEval memory design stages?' --arm rag
python3 research_lab.py ask 'What are LongMemEval memory design stages?' --arm replay
```

`consolidate` processes **all** pending chunks in batches; it has no first-six-chunks pilot option. Original sources remain in the database. `ask` returns an answer with retrieved evidence and paper IDs; it does not store that question or answer. There is no timer or background worker.

## 6. Share the evidence carefully

```bash
python3 research_lab.py export results/first-pilot.json --out artifacts/my-first-pilot.json
```

The export replaces original evidence passages with hashes. It retains model answers and interpretations, which may themselves quote source text. Inspect the export before committing it; do not publish the paper cache, local SQLite database, credentials or private logs. Third-party papers retain their own licenses.

When finished with the terminal credential:

```bash
unset OPENAI_API_KEY
```

See [CLI reference](CLI.md) for options and recovery, [architecture](ARCHITECTURE.md) for provenance, and [the recorded pilot](../artifacts/RESULTS.md) for an example of honest results reporting.
