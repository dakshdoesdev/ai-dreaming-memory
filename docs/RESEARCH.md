# Research basis and evaluation boundaries

Primary sources checked on 13 November 2026. These notes summarize published work; they are not results from this project. Paper versions below were verified against arXiv submission histories. Repository documentation can change independently of a paper version.

## Sources

| Paper | Pinned version | Role in this experiment |
| --- | --- | --- |
| Hu, Wang and McAuley, *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions* | [2507.05257v4](https://arxiv.org/abs/2507.05257v4), 28 June 2026 | Incremental ingestion and capability-specific evaluation |
| Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory* | [2410.10813v2](https://arxiv.org/abs/2410.10813v2), 4 March 2025 | Separate indexing, retrieval and answer generation |
| Packer et al., *MemGPT: Towards LLMs as Operating Systems* | [2310.08560v2](https://arxiv.org/abs/2310.08560v2), 12 February 2024 | Persistent storage outside a finite model context |
| Sumers et al., *Cognitive Architectures for Language Agents* | [2309.02427v3](https://arxiv.org/abs/2309.02427v3), 15 March 2024 | Distinguish retrieval, reasoning and memory updates |

### MemoryAgentBench

**Method.** The authors convert long inputs into incremental text chunks, then evaluate different memory systems on shared histories. Paper v4 organizes tasks around accurate retrieval, test-time learning, long-range understanding and selective forgetting. Its experiments include lexical BM25, dense retrieval and agentic memory approaches. **Reported finding.** The authors conclude that evaluated methods do not master every capability; chunk size, retrieved context and memory-construction cost affect comparisons. **Author-stated limitation.** Budget constraints restricted the set of evaluated agents. These claims do not establish how DeepSeek on Token Lab will perform. See [Sections 3–5 and Appendices C, E–I](https://arxiv.org/html/2507.05257v4).

The [official repository README](https://github.com/HUST-AI-HYZ/MemoryAgentBench) calls the fourth capability **conflict resolution**, while paper v4 uses **selective forgetting**. The repository also assigns different metrics to different datasets: exact match, substring match, Recall@5 or a model judge. A custom paper-QA pilot is not an official MemoryAgentBench run, and its scores must not be presented as directly comparable.

### LongMemEval

**Method.** The authors build 500 questions across information extraction, multi-session reasoning, temporal reasoning, knowledge updates and abstention. Their framework separates indexing, retrieval and reading. **Reported finding.** They report benefits from finer session decomposition, fact-augmented indexing and time-aware queries. They also warn that summary/fact compression can lose details needed for answering. **Evaluation boundary.** The benchmark evaluates conversational memory; it does not validate scientific claims or real-world task execution. Its answer scoring uses a task-specific model judge rather than this project's simple alias rubric. See [Sections 3–5](https://arxiv.org/html/2410.10813v2).

The [official repository](https://github.com/xiaowu0162/LongMemEval) identifies cleaned histories and a newer V2 benchmark. Any later integration should pin the dataset revision, rather than silently mixing paper-era and updated data.

### MemGPT

**Method.** MemGPT moves information between a finite main context and external recall/archival storage through model-controlled function calls. It summarizes evicted queue contents while retaining messages in recall storage. **Reported finding.** The authors report gains on conversational memory and document-analysis tasks in their settings. **Boundary.** They identify retrieval failures when useful documents rank too low. The architecture is a motivation for persistent storage, not evidence that this project's scheduled compression or generated replay will improve accuracy. See [Section 2 and Section 3.2](https://arxiv.org/html/2310.08560v2).

### CoALA

**Method.** CoALA is a conceptual framework separating memory, internal/external actions and decision procedures. Retrieval reads long-term memory into working memory; reasoning transforms working-memory contents; learning can update persistent memory without changing model weights. **Author-proposed gaps.** The paper identifies adaptive recall, integration of retrieval with decision-making, and interactions between forms of learning as research directions. **Boundary.** This is an organizing framework and survey, not a controlled demonstration of the proposed experiment. Cognitive terminology does not imply biological equivalence. See [Sections 4, 6 and 7](https://arxiv.org/html/2309.02427v3).

## Design choices for this project

These are experimental safeguards, not established findings:

1. Freeze the collected corpus, arXiv versions, text hashes, chunking settings and question file before evaluation. Record model ID, seed, retrieval count, context budget and code revision.
2. Keep held-out questions, expected answers and rubrics outside ingestion, extraction, consolidation and replay prompts. Do not store benchmark answers back into memory.
3. Compare raw RAG, raw RAG plus compact memory, and raw RAG plus compact memory and replay. Hold the answering model and answer prompt fixed. Generated replay is retrieved data, not model fine-tuning.
4. Report extraction/consolidation cost separately from per-question cost. Extra model calls are part of a mechanism's cost, even when amortized across questions. Character limits are only an approximation to matched token budgets.
5. Preserve original evidence. Require quotes and source IDs for extracted claims; quote matching validates provenance, not the interpretation or truth of a claim. Keep author-reported gaps distinct from model-suggested research ideas.
6. Measure answer accuracy, supporting-source retrieval and task-constraint satisfaction separately. Inspect stale facts, missing detail, invalid citations and confidently wrong answers, including failures introduced by compression.
7. Include unanswerable questions. A model should abstain when the corpus does not supply the requested fact.
8. Audit string-based grades manually before publication. Correct paraphrases can fail a rubric, and wrong answers containing the expected words can pass it.
9. Report paired differences and uncertainty over independent papers or independent task groups. Repeated calls on the same four papers do not create a large independent sample; overlapping multi-paper questions also create dependence.
10. Treat null and negative results as valid. A small pilot can demonstrate implementation and expose failure modes; it cannot establish broad superiority over ordinary RAG, dense/hybrid RAG, other models or official memory benchmarks.

## What remains unestablished

Until authenticated model runs are completed, offline smoke outputs demonstrate orchestration only. Textual task rubrics are proxies for task completion; no external research task is executed automatically. A useful next study would use independent, preregistered paper sets and expert-audited questions, vary context budgets, and include a dense or hybrid retrieval baseline. Claims about genuine scientific discovery, model learning, or biological dreaming are outside this experiment's scope.
