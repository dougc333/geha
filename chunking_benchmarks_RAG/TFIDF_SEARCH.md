# Whole-policy TF-IDF search

`tfidf_policy_search.py` is a read-only lexical-search baseline over the 32
top-level `geha-coverage-policy-*.docling.md` files. It removes revision-history
sections and `Date / Updates` tables before indexing. Each policy is one TF-IDF
document; no PostgreSQL table, embedding model, API key, or database rebuild is
required.

From the repository root:

```bash
/Users/dc/geha/.venv/bin/python chunking_benchmarks_RAG/tfidf_policy_search.py \
  'Which GEHA policy has approval criteria for chemotherapy-induced thrombocytopenia?'
```

Use `--top-k 10` to show more policies or `--policy-dir PATH` to search another
directory. Scores are cosine similarity between L2-normalized TF-IDF vectors;
they rank lexical relevance, not coverage eligibility or probability of truth.
The current Streamlit table search is unchanged. Evaluate this baseline against
the existing policy-retrieval cases before deciding whether to route app queries
through it.

Run the regression tests without pytest:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/dc/geha/.venv/bin/python -m unittest discover \
  -s chunking_benchmarks_RAG -p 'test_tfidf_policy_search.py' -v
```
