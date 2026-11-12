# Initial study protocol

## Question and scope

Does adding compressed memory, or compressed memory plus synthetic replay, improve answer correctness relative to raw lexical RAG for a fixed paper corpus and context character budget?

The pilot collects full text from four pinned arXiv papers but evaluates **only the first six chunks of each paper**. Chunks contain at most 1200 original text characters plus a paper/title header. A source audit confirmed that the required terms for all ten answerable questions are present in this prefix. Two additional questions require abstention. These are mostly abstract/introduction questions, not a deep scientific reasoning benchmark.

The question file was written before model evaluation. Its initial rubric and source implementation were committed in `61e4b12` before outcomes were observed. A subsequent pre-run correction made abstention grading exact: an answer containing UNKNOWN alongside fabricated content cannot pass.

## Controls

- Same DeepSeek model, fixed answer prompt, temperature zero, top-k=4 and 2400-character evidence budget for all arms.
- Separate BM25 corpus statistics for raw, raw+summary, and raw+summary+replay arms.
- No held-out questions or rubric answers in extraction/consolidation prompts.
- No benchmark answers written back into memory; temporary indexes are isolated from the persistent collection database.
- Seeded arm-order randomization. Shared consolidation cost is reported separately from answering cost.
- Full text retained locally; paper IDs, versions, text/chunk hashes and model usage recorded.

The same papers intentionally supply the indexed evidence and the subjects of held-out questions. That is the retrieval-memory task. Holding out source papers entirely would measure a different generalization problem. Public papers may already be represented in model pretraining, so this pilot cannot prove that any answer depends solely on newly acquired memory.

## Measurements and interpretation

Recall and research-brief success use predefined alias groups, while abstention requires the exact normalized response UNKNOWN. Report supporting-paper retrieval recall separately; it is not answer-citation accuracy or passage-level evidence recall. Paired differences are exploratory. The four papers and overlapping comparison tasks provide too few independent support clusters for a reliable population confidence interval.

Review all model answers against source evidence. Term matching cannot reliably verify attribution, negation or meaningful comparison; for example, a cross-paper answer can contain every expected term without assigning them to the right paper. Preserve both positive and negative outcomes. Do not tune the rubric after inspecting outcomes and then present the rerun as confirmatory.

Raw RAG uses no consolidation calls. Summary and replay are generated together, so generation costs cannot be cleanly separated between those two arms. The fixed character budget approximates model context usage; API token usage is also recorded. Replay is synthetic text in a retrieval index, not model weight training.

## Scaling beyond the pilot

Run full-text extraction/evaluation by omitting the explicit prefix option. Before making a general claim, use independent paper sets, expert-authored tasks with attribution/citation scoring, repeated trials and several context budgets. Add dense/hybrid retrieval and evidence-matched controls. Report failure rates, total preprocessing+answering cost, and whether any gain survives these controls.

Exact evidence validation prevents invented quote strings but does not establish scientific truth or correct discourse attribution. Author-reported gaps remain model interpretations requiring review. Downloaded full texts retain their original licenses and are not included in the repository.
