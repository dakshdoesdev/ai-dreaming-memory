# DeepSeek paper-memory pilot

**One completed live pilot, not a general benchmark claim.** DeepSeek-V4-Flash was called through AMD Token Lab on 13 November 2026 (local time). The protocol used seed 42, temperature zero, top-k 4 and a 2400-character retrieved-evidence budget. Source implementation: `5c0bf9d3da7ee20aa6aede113c203acdfd0ea729`.

Full text was collected for four version-pinned papers (333 chunks). The experiment used only the first six chunks per paper: **24 chunks and 12 fixed questions**. All test-answer terms were source-supported within that prefix. Questions/rubrics were held out of memory construction.

## Automatic rubric results

| Arm | All checks | Recall | Research-brief constraints | Abstention |
| --- | ---: | ---: | ---: | ---: |
| Raw RAG | 5/12 (41.7%) | 3/6 | 0/4 | 2/2 |
| RAG + compressed memory | 10/12 (83.3%) | 5/6 | 3/4 | 2/2 |
| RAG + memory + replay | 10/12 (83.3%) | 5/6 | 3/4 | 2/2 |

Consolidation improved the predefined rubric pass count in this small run. **Replay provided no additional rubric improvement.** This is not evidence of broad superiority over RAG. There are only three connected support clusters; the implementation suppresses a confidence interval rather than reporting misleading precision.

## Rubric audit

The published scores retain the original rubric; it was not changed after seeing answers. Post-run textual review identified clear false negatives:

- All three arms described CoALA's memory/storage, action space and decision-making elements, but the rubric demanded a narrower memory phrase.
- Raw RAG correctly returned “conversational agents” for a MemGPT evaluation domain, while the rubric accepted only “multi-session chat.”
- The memory arms described hierarchical memory/paging correctly in a comparison task but omitted the explicitly requested technique name; this remains a strict task failure.

These examples mean the table measures **literal rubric pass rate**, not expert-verified factual accuracy. As an illustrative post-hoc sensitivity check only, accepting the four clear synonym cases would give 7/12 for raw RAG and 11/12 for each memory arm. That is not the preregistered primary score or an independent validation.

## Cost and latency

| Arm | Answering input tokens | Answering output tokens | Answering time, 12 calls |
| --- | ---: | ---: | ---: |
| Raw RAG | 4,451 | 387 | 41.0 s |
| Compressed memory | 6,476 | 357 | 35.6 s |
| Memory + replay | 7,056 | 390 | 70.6 s |

Shared memory/replay preprocessing required 4 additional calls: 16,935 input tokens, 2,016 output tokens and 39.0 seconds. Raw RAG does not need those calls. The two memory arms share their generated records; construction costs are not independently isolated.

Equal characters did **not** give equal token usage: compressed-memory answering used more input tokens than raw RAG. Character-vs-token allocation and preprocessing cost prevent a token-efficiency claim. Times include client pacing and hosted API wait time; one run cannot establish hardware throughput or stable latency.

Four earlier setup attempts failed provenance/serialization validation during memory construction, before answer scoring began. They are not completed benchmark trials. The table covers the completed study only; development/setup calls are not included in its costs.

## Extraction and persistence

The first-six-chunks extraction completed for all four papers and produced **97 candidate claims**. Full-paper extraction remains partial by design. A textual spot audit flagged four invalid gap classifications (including no-gap placeholders and excerpt-boundary inferences); all candidates require scientific review. Exact evidence reconstruction validates source spans, not interpretation.

A separate live consolidation call persisted six compact memories and six replay records alongside all 333 original chunks. The remaining 327 raw chunks are pending consolidation; this is not a claim that the full corpus was consolidated.

## Artifacts and reproduction

- [Live answers, metrics and provenance hashes](deepseek-pilot.json)
- [Extraction candidates with review flags](deepseek-extractions.json)
- [Extraction audit](EXTRACTION_AUDIT.md)
- [Persistent-memory status and usage](persistent-memory-status.json)
- [Versioned corpus manifest](corpus-manifest.json)
- [Protocol and limitations](../docs/EXPERIMENT.md)

```bash
python3 -m unittest discover -v
python3 research_lab.py collect
python3 research_lab.py extract --max-chunks-per-paper 6 > data/extraction.json
python3 research_lab.py evaluate --max-chunks-per-paper 6 --out results/reproduction.json
```

Use a fresh output path and set Token Lab credentials as described in the README. Original retrieved passages are replaced with hashes in public JSON; regenerate the pinned local corpus to inspect them. Model aliases and hosted inference can change, so identical seeds do not guarantee identical answers.

This is a custom, shallow paper-QA pilot rather than an official MemoryAgentBench run or real external task execution. Public papers may be in model pretraining. Larger independent paper sets, expert-audited attribution/citation scoring, repeated trials, multiple budgets and stronger retrieval baselines are needed before a general claim.
