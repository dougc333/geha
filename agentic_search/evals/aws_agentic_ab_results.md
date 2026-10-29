# AWS corrective RAG A/B evaluation

Questions: 22

| Metric | Single search | Corrective | Change |
| --- | ---: | ---: | ---: |
| Fact recall | 56.1% | 63.2% | +7.0 pp |
| Source recall | 57.9% | 57.9% | +0.0 pp |
| Complete-answer rate | 4.5% | 22.7% | +18.2 pp |
| Grounded-answer rate | 63.6% | 54.5% | -9.1 pp |
| Correct abstention rate | 0.0% | 0.0% | +0.0 pp |
| Follow-up-search rate | 0.0% | 95.5% | +95.5 pp |
| Mean retrieval rounds | 1.00 | 1.95 | +0.95 |
| Mean generation attempts | 1.41 | 1.50 | +0.09 |
| Median latency | 4458 ms | 6887 ms | +2429 ms |
| p95 latency | 6851 ms | 9578 ms | +2727 ms |

Fact recall is judged in one batched Nova call per answer against the checked-in rubric facts. 
Source recall is calculated from retrieved document IDs. Report numerators and inspect the JSON 
records before making quality claims; this evaluation set is small.
