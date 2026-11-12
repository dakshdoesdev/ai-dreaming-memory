# Extraction spot audit

This is an automated textual consistency check of stored model claims and their evidence, not expert or human validation. It does not establish completeness or scientific truth.

The prefix study covers the first six chunks of each paper. An author-reported research motivation is different from a residual limitation of that paper's own proposed method. The current `gap_origin` field alone does not capture that distinction.

| Paper | Source message | Stored gap interpretation | Audit verdict |
| --- | ---: | --- | --- |
| CoALA | 227 | Missing framework for organizing language agents | Supported field motivation; not a demonstrated remaining limitation of CoALA |
| CoALA | 229 | Fragmented terminology impedes comparison | Supported field motivation; evidence segment ends mid-word |
| MemGPT | 185 | Alternatives to context scaling are needed | Supported field motivation; not a demonstrated remaining limitation of MemGPT |
| MemGPT | 186 | The excerpt reports no explicit gap | Invalid placeholder; exclude from substantive gap counts |
| LongMemEval | 1 | Sustained conversational memory remains underexplored | Supported field motivation; not proof that the proposed benchmark leaves it unresolved |
| LongMemEval | 5 | A cut-off excerpt leaves a framework incomplete | Invalid excerpt-boundary inference; not a scientific gap |
| MemoryAgentBench | 89 | A cut-off dataset discussion implies a limitation | Invalid excerpt-boundary inference |
| MemoryAgentBench | 90 | LongMemEval addresses a previous limitation | A solution description; not a gap |

The completed prefix extraction contains 97 model-generated candidate claims. Four gap classifications are flagged as rejected in the public export. Other gap candidates still require scope review. Raw model records are retained for auditability; the counts are not counts of validated discoveries. Prompt instructions and exact source spans do not guarantee correct claim classification. Before using these outputs in a literature review, inspect the complete source sections and separate field motivations, author-reported limitations and model-inferred ideas.
