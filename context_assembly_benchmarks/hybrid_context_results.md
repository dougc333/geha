# Hybrid retrieval context comparison

### Hybrid retrieval context comparison

All strategies use the same BM25 + pgvector RRF child ranking. Table-aware + attached notes adds the paragraph before and the notes after each parent table from the verified document (footnotes, exceptions, authorization period).

| Question slice | Context strategy | Cases | Avg evidence coverage | Complete evidence | Qualifier coverage | Expected table present | Avg estimated tokens | Avg sibling rows | Evidence / 1k tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | Flat semantic chunks | 59 | 72.6% | 40.7% | 0.0% | 98.3% | 299 | 2.7 | 7.43 |
| Overall | Table-aware RAG | 59 | 87.7% | 69.5% | 0.0% | 100.0% | 476 | 14.5 | 6.05 |
| Overall | Table-aware + attached notes | 59 | 100.0% | 100.0% | 100.0% | 100.0% | 814 | 14.5 | 3.92 |
| Preference | Flat semantic chunks | 34 | 81.4% | 58.8% | — | 97.1% | 285 | 2.7 | 7.22 |
| Preference | Table-aware RAG | 34 | 100.0% | 100.0% | — | 100.0% | 407 | 12.7 | 7.08 |
| Preference | Table-aware + attached notes | 34 | 100.0% | 100.0% | — | 100.0% | 745 | 12.7 | 3.87 |
| Relation | Flat semantic chunks | 7 | 83.3% | 57.1% | — | 100.0% | 330 | 0.7 | 15.15 |
| Relation | Table-aware RAG | 7 | 100.0% | 100.0% | — | 100.0% | 558 | 6.3 | 10.76 |
| Relation | Table-aware + attached notes | 7 | 100.0% | 100.0% | — | 100.0% | 984 | 6.3 | 6.09 |
| Qualifier | Flat semantic chunks | 18 | 51.9% | 0.0% | 0.0% | 100.0% | 313 | 3.4 | 4.62 |
| Qualifier | Table-aware RAG | 18 | 59.7% | 0.0% | 0.0% | 100.0% | 574 | 21.0 | 2.90 |
| Qualifier | Table-aware + attached notes | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 877 | 21.0 | 3.04 |

Table-aware change versus flat chunks: average evidence coverage +15.1%, complete evidence +28.8%, and average context tokens +177.

This is a retrieval/context benchmark over labeled expected values. It does not use an LLM judge and does not measure generation quality.
