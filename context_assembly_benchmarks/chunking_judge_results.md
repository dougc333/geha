# Answer completeness by context strategy (per-fact join with context completeness)

- Queries completed: 59/59
- Answer model: gpt-4o-mini; judge and fact-check model: gpt-4o-mini
- Total answer + judge + fact-check tokens: 422,507

| Slice | Strategy | Cases | Context complete | Answer complete | Judge YES | Cases with assembly error | Cases with generation drop | Facts: correct / drop / assembly / unsupported | Avg context tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| overall | Flat semantic chunks | 59 | 40.7% | 40.7% | 30.5% | 59.3% | 5.1% | 128 / 3 / 57 / 0 | 299 |
| overall | Table-aware RAG | 59 | 69.5% | 69.5% | 64.4% | 27.1% | 6.8% | 164 / 6 / 16 / 2 | 476 |
| overall | Table-aware + attached notes | 59 | 100.0% | 93.2% | 81.4% | 0.0% | 6.8% | 182 / 6 / 0 / 0 | 896 |
| Preference lookup | Flat semantic chunks | 34 | 58.8% | 58.8% | 44.1% | 41.2% | 2.9% | 69 / 1 / 28 / 0 | 285 |
| Preference lookup | Table-aware RAG | 34 | 100.0% | 94.1% | 85.3% | 0.0% | 5.9% | 95 / 3 / 0 / 0 | 407 |
| Preference lookup | Table-aware + attached notes | 34 | 100.0% | 94.1% | 82.4% | 0.0% | 5.9% | 95 / 3 / 0 / 0 | 826 |
| Row-to-column relationship | Flat semantic chunks | 7 | 57.1% | 57.1% | 42.9% | 42.9% | 0.0% | 35 / 0 / 7 / 0 | 330 |
| Row-to-column relationship | Table-aware RAG | 7 | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 42 / 0 / 0 / 0 | 558 |
| Row-to-column relationship | Table-aware + attached notes | 7 | 100.0% | 100.0% | 85.7% | 0.0% | 0.0% | 42 / 0 / 0 / 0 | 1071 |
| Qualifier | Flat semantic chunks | 18 | 0.0% | 0.0% | 0.0% | 100.0% | 11.1% | 24 / 2 / 22 / 0 | 313 |
| Qualifier | Table-aware RAG | 18 | 0.0% | 11.1% | 11.1% | 88.9% | 11.1% | 27 / 3 / 16 / 2 | 574 |
| Qualifier | Table-aware + attached notes | 18 | 100.0% | 88.9% | 77.8% | 0.0% | 11.1% | 45 / 3 / 0 / 0 | 960 |

Each required fact is checked in the context and in the answer: an assembly error is a fact the context never contained; a generation drop is a fact the model had and left out. The same answer model, judge rubric and fact checker are used for every strategy. LLM judgments remain evaluation signals rather than ground truth.
