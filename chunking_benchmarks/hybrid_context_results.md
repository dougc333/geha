# Hybrid retrieval context comparison

### Hybrid retrieval context comparison

Both cases use the same BM25 + pgvector RRF child ranking.

| Question slice | Context strategy | Cases | Avg evidence coverage | Complete evidence | Expected table present | Avg estimated tokens | Evidence / 1k tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | Flat semantic chunks | 41 | 81.7% | 58.5% | 97.6% | 292 | 8.76 |
| Overall | Table-aware RAG | 41 | 100.0% | 100.0% | 100.0% | 431 | 7.92 |
| Preference | Flat semantic chunks | 34 | 81.4% | 58.8% | 97.1% | 285 | 7.22 |
| Preference | Table-aware RAG | 34 | 100.0% | 100.0% | 100.0% | 405 | 7.12 |
| Relation | Flat semantic chunks | 7 | 83.3% | 57.1% | 100.0% | 328 | 15.24 |
| Relation | Table-aware RAG | 7 | 100.0% | 100.0% | 100.0% | 558 | 10.76 |

Table-aware change versus flat chunks: average evidence coverage +18.3%, complete evidence +41.5%, and average context tokens +139.

This is a retrieval/context benchmark over labeled expected values. It does not use an LLM judge and does not measure generation quality.
