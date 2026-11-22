# Minimal document graph example

All values are **synthetic teaching data**, not findings from Georgetown, EY,
or any other real report. The example uses only Python's standard library.

```bash
cd /Users/dc/geha/crawl_dir/examples/benefits_document_graph
python demo.py query --mode query-time
python demo.py build
python demo.py query --mode prebuilt
```

Both queries start from the `overview` document and answer the same question:
compare access to paid leave in retail and manufacturing. Both select the same
two reports and pass the same two cited observations to an answer LLM.

| Step | Query-time | Prebuilt |
| --- | --- | --- |
| Candidate discovery | Rechecks every document profile on each query | Follows the saved `paid_leave` link in `graph.json` |
| Relationship judgment | `judge_relation()` checks profile comparability | Same check on linked candidates |
| Answer context | Only selected observations | Only selected observations |

`graph.json` stores document IDs, not full PDF text. `answer_context()` loads
only selected evidence for the final comparison. In a real pipeline,
`judge_relation()` can be replaced with an LLM call that sees compact document
profiles and returns an inclusion decision with a reason. The numerical claims
still require page evidence before they enter `answer_context()`.

This small example does not model conflicting definitions, study quality, or
time-varying results. Those should become explicit relationship types and
comparison checks in a production document graph.
