# MiMo-V2.5 via Nous dental benchmark

Same six questions, corpus, answer prompt and bounded graph as Gemma.
MiMo judges its own answers; scores are not human-validated accuracy.
JSON-object output is validated locally; unlike Google, no response schema is sent.
Sequential calls without the Google-specific 14-second delay; retries included in latency.

| Retrieval | Workflow | Completed | Rubric completeness | Supported citations | Median seconds |
|---|---|---:|---:|---:|---:|
| bm25 | one_pass | 2/6 | 60.0% | 2/2 | 40.4 |
| bm25 | agentic | 2/6 | 60.0% | 2/2 | 57.5 |
| vector | one_pass | 1/6 | 80.0% | 1/1 | 48.9 |
| vector | agentic | 2/6 | 80.0% | 2/2 | 64.8 |
| hybrid | one_pass | 2/6 | 80.0% | 1/2 | 34.7 |
| hybrid | agentic | 1/6 | 60.0% | 0/1 | 50.2 |

Completed: 10/36; errors: 1.
Paid Nous inference; full usage metadata saved in mimo_nous_answers.jsonl.
Cross-model self-judging and different pacing confound comparisons with Gemma.
