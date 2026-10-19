# GEHA retriever fine-tuning

DEMO ONLY! This uses 2 pdfs. This data set is too small to get meaningful results. 

This experiment fine-tunes `BAAI/bge-base-en-v1.5` for GEHA dental-policy
retrieval with `MultipleNegativesRankingLoss`. It uses section-disjoint training
and validation splits from the benefits guide and a separate plan brochure as
the held-out test document.

## Held-out test results

The 41-question test uses 167 candidate chunks. The measured changes from one
three-epoch run were:

| Metric | Base model | Fine-tuned | Absolute change |
| --- | ---: | ---: | ---: |
| Recall@5 | 64.63% | 68.70% | +4.07 points |
| MRR@10 | 72.61% | 72.72% | +0.11 points |
| nDCG@10 | 67.74% | 70.01% | +2.27 points |

These are preliminary results from two related public dental documents, not a
claim of general improvement. Repeat the experiment across seeds and additional
held-out documents before promoting the encoder; domain fine-tuning can regress
performance outside this evaluation distribution.

This directory contains the isolated environment and programs used to create
training and evaluation data for domain-specific retrieval. It is deliberately
separate from the repository's shared `.venv`: RAGAS 0.4.3 requires OpenAI
below 2 and Rich below 15, while the main GEHA applications use newer versions.

## Files

- `generate_ragas_qa.py` loads the canonical token-safe dental chunks and uses
  RAGAS to generate questions, reference answers, and reference contexts.
- `prepare_retriever_splits.py` removes table-of-contents artifacts and creates
  section-disjoint train/validation splits plus a document-disjoint test set.
- `train_retriever.py` fine-tunes the encoder and selects the best validation
  checkpoint.
- `finetuning.ipynb` records baseline evaluation, training, and the held-out
  before/after comparison.
- `requirements.txt` pins the compatible RAGAS/LangChain dependency family.
  It also includes `rapidfuzz`, an optional package required by RAGAS's default
  entity-overlap transform but omitted from the base RAGAS installation.
- `tests/test_generate_ragas_qa.py` verifies filtering, provenance matching,
  and compact QA output without making model calls.
- `.venv/` is the ignored, local Python environment for these utilities.

## Environment setup

```bash
cd /Users/dc/geha/finetuning

uv venv .venv --python 3.12
uv pip install \
  --python .venv/bin/python \
  -r requirements.txt
```

Load the OpenAI key already stored in `.zshrc`:

```bash
source ~/.zshrc
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY is set"
```

## Generate the QA pairs

First validate the 205-line input. The default 100-character filter retains
203 useful chunks and removes two short artifacts. A dry run makes no API
calls:

```bash
cd /Users/dc/geha/finetuning
.venv/bin/python generate_ragas_qa.py --dry-run
```

Generate 50 samples:

```bash
source ~/.zshrc
cd /Users/dc/geha/finetuning
.venv/bin/python generate_ragas_qa.py --testset-size 50
```

The generator limits RAGAS to four concurrent workers and retries transient API
connection failures. If the network remains unstable, resume with one worker:

```bash
.venv/bin/python generate_ragas_qa.py \
  --testset-size 50 \
  --max-workers 1 \
  --max-retries 15
```

The defaults are `gpt-4.1-mini` for question/reference-answer generation and
`text-embedding-3-small` for RAGAS transformations. Override them with
`--model` and `--embedding-model`.

The default source is:

```text
/Users/dc/geha/crawl_dir/runs/dental/
fedvip--2026-geha-dental-plan-brochure/
batch-20261009-token-safe/candidate/chunks.jsonl
```

Outputs are written beside that source:

```text
candidate/ragas/
├── ragas_testset.jsonl  # native RAGAS fields plus chunk provenance
└── qa_pairs.jsonl       # compact question/answer/context records
```

The output is evaluation data, not a vector index and not a completed retriever
training dataset. Review every generated pair, keep the final benchmark held
out, and mine verified hard-negative chunks separately before fine-tuning.

## Tests

```bash
cd /Users/dc/geha
finetuning/.venv/bin/python -m unittest \
  finetuning.tests.test_generate_ragas_qa \
  finetuning.tests.test_prepare_retriever_splits -v
```

## Run the experiment

Create the local, ignored source splits first:

```bash
cd /Users/dc/geha
finetuning/.venv/bin/python -m finetuning.prepare_retriever_splits
```

Generate reviewed training and validation QA pairs with
`generate_ragas_qa.py`, then run the trainer:

```bash
cd /Users/dc/geha
source finetuning/.venv/bin/activate
python finetuning/train_retriever.py
```

The compact synthetic QA JSONL files are committed as reproducible training and
benchmark fixtures. Source chunks, native RAGAS intermediates, models, and
evaluator checkpoints remain ignored; regenerate those locally from the source
documents.
