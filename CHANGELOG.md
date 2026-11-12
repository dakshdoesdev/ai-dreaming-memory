# Changelog

Changes are recorded here without implying a published package release.

## Unreleased

### Added

- Version-pinned arXiv metadata and full-text collection with caching, content hashes, HTML extraction and a PDF text fallback.
- SQLite storage for original paper chunks, conversation history, compact memories and synthetic replay records.
- DeepSeek integration through AMD Token Lab, with environment-based credentials, paced requests and bounded retries.
- Source-constrained structured extraction of candidate methods, findings and author-reported gaps, with resumable per-chunk checkpoints.
- Periodic consolidation during isolated paper evaluation and explicit consolidation commands for persistent stores.
- A three-arm lexical BM25 comparison: raw RAG, raw plus compressed memory, and raw plus memory and replay.
- Held-out question validation, corpus and question hashes, per-category rubric scores, source provenance, usage and latency reporting.
- Offline smoke workflows and standard-library regression tests, with CI on Python 3.11, 3.12 and 3.13.
- Public exports that replace original source passages with hashes while retaining model answers and candidate interpretations.
- A recorded four-paper prefix pilot, extraction spot audit and persistent-memory verification in [the results artifacts](artifacts/RESULTS.md).

### Reliability checks

- Validate source IDs and reconstruct exact covering evidence spans from selected segments.
- Request constrained JSON Schema output for known consolidation and extraction prompts; retain local validation before saving records.
- Preserve validated extraction checkpoints when a later chunk fails.
- Keep held-out evaluation answers out of the memory index and reject unfinished reports during export.
- Reserve output paths before inference and preserve existing reports.

### Known limitations

- The recorded pilot evaluates six chunks per paper and twelve questions; it is not a full-paper study or an official MemoryAgentBench run.
- Literal rubric matching has documented false negatives, and source-backed candidate claims can still be misinterpreted or misclassified.
- Replay is retrieved text, not model weight training. Textual task checks do not execute external research tasks.
- Character budgets do not equal token budgets. Memory construction adds model calls, and shared summary/replay costs are not independently isolated.
- Hosted model aliases and inference can change; a fixed seed does not guarantee identical future answers.
