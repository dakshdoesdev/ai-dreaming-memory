# Contributing

Contributions should make the experiment easier to reproduce, inspect or evaluate. Keep changes focused, preserve original evidence, and report negative results as carefully as positive ones.

Start with the [README](README.md), [architecture](docs/ARCHITECTURE.md), [CLI reference](docs/CLI.md) and [experiment protocol](docs/EXPERIMENT.md).

## Local development

Use Python 3.11 or newer with SQLite FTS5. The application and test suite use the Python standard library; there is no Python package installation step. Poppler's `pdftotext` is only needed for collecting papers without usable HTML.

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v
PYTHONDONTWRITEBYTECODE=1 python3 research_lab.py --help
PYTHONDONTWRITEBYTECODE=1 python3 memory_lab.py --help
git diff --check
```

Unit tests use temporary stores and mocked network responses. They do not need an API key or internet access. CI runs the tests on Python 3.11, 3.12 and 3.13 and checks that application modules compile.

For a larger offline workflow check, choose a new output filename:

```bash
python3 memory_lab.py --offline evaluate --out results/contributor-smoke.json
```

The smoke model always answers `UNKNOWN`. Its scores are plumbing checks, not scientific results. The paper smoke workflow additionally needs a locally collected corpus; see the [CLI reference](docs/CLI.md).

## Change boundaries

- Reuse existing modules and standard-library tools before adding dependencies. Discuss any proposed runtime dependency before introducing it.
- Add a focused regression test when changing nontrivial behavior, especially source validation, persistence, scoring or evaluation isolation.
- Keep documentation, examples and CLI help consistent with the code. Documentation-only changes should not require paid model calls.
- Keep the original paper text available locally when changing memory behavior. Do not silently replace a pinned corpus version or reinterpret its hash.
- Keep generated memories and extracted claims distinct from primary source evidence. A valid source span does not establish a scientifically correct interpretation.

## Experimental integrity

Freeze the corpus, question file, rubric and settings before a comparison. Record paper versions, hashes, model identifier, source revision, retrieval settings and corpus scope. Hold evaluation questions and expected answers out of memory construction; never store benchmark answers back into the evaluation index.

When changing an experiment:

1. Use a new report path. Existing completed reports are evidence, not files to edit until a score improves.
2. Label prefix coverage explicitly. Collecting full papers does not mean a first-six-chunks evaluation analyzed them in full.
3. Include raw model answers, scoring limitations and preprocessing costs. Public exports can replace source passages with hashes.
4. Keep post-hoc rubric reviews separate from the original score. Do not present revised scoring or tuned prompts as an untouched confirmatory run.
5. Avoid general claims from the small pilot. This project does not run the official MemoryAgentBench suite, and its task checks do not execute external research tasks.

The [recorded results](artifacts/RESULTS.md) demonstrate how to report rubric false negatives, extraction errors and the absence of an additional replay gain.

## Credentials and publication

Live model calls are optional for development. Configure credentials in your shell as described in the README; never put a key in source files, screenshots, issue reports or commits. Model calls send selected paper text to AMD Token Lab and use the account's points.

Keep downloaded papers, local databases, caches, `.env` files and private run logs out of Git. `data/` and `results/` are ignored. Review staged paths before committing:

```bash
git diff --cached --stat
git diff --cached
```

The `export` command redacts original `text` and `evidence` fields but preserves generated answers and interpretations. Inspect those outputs for sensitive information, long copied passages and unsupported claims before publishing. Third-party papers retain their own licenses.

## Commits and pull requests

Use a separate branch for a focused change. Begin a commit message with its intent: why the change is needed. Add the verification and constraints that help a reviewer understand it, using native Git trailers when useful:

```text
Keep evaluation instructions aligned with prefix coverage

Explain the scope option before the example command so a new run
does not accidentally imply full-paper analysis.

Tested: CLI help and relative documentation links
Not-tested: Live Token Lab inference; documentation-only change
Scope-risk: narrow
```

In a pull request, describe the user-visible change, checks run and known gaps. For experiment changes, include the exact command and settings, explain whether the rubric changed, and link the corresponding results. For documentation or visual changes, include a readable preview and identify the source data behind charts.
