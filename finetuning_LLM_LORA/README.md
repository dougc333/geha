# GEHA generator LoRA finetuning

Instruction-finetunes the **answer generator** of the GEHA dental RAG pipeline
with LoRA. This is the generator half of RAG finetuning; the retriever half
(contrastive training of `bge-base`) lives in [`../finetuning`](../finetuning).

| | |
| --- | --- |
| Base model | `Qwen/Qwen2.5-1.5B-Instruct` |
| Method | LoRA, r=16, alpha=32, dropout 0.05, on all attention + MLP projections (~1% of weights trainable) |
| Loss | Next-token cross-entropy on **assistant tokens only** (system prompt, passages and question are masked) |
| Data formats | `direct` (passages + question → answer) and `cot` (passages + question → quoted evidence → answer), mixed in one run as in FLAN multi-task instruction finetuning ([arXiv 2210.11416](https://arxiv.org/abs/2210.11416)) |
| Context | Gold passage(s) + 2 distractor chunks, shuffled (RAFT-style), so the model learns to ignore irrelevant retrieval |
| Checkpoint selection | Lowest validation loss, evaluated every 10 optimizer steps and at every epoch end |

## Data splits

Full report: [`results/data_splits.md`](results/data_splits.md) (regenerate with
`split_stats.py --tokenizer`).

| | train | validation | test |
| --- | ---: | ---: | ---: |
| Source document | 2026 benefits guide | 2026 benefits guide | 2026 plan brochure |
| Sections | 22 | 6 | 72 |
| Chunks (distractor pool) | 34 | 8 | 167 |
| QA pairs | 78 | 24 | 41 |
| SFT examples (direct + cot) | 156 | 48 | 82 |
| Prompt tokens min/mean/max | 330/990/2157 | 313/702/997 | 580/1251/2042 |
| Target tokens min/mean/max | 15/135/335 | 27/120/316 | 31/199/427 |

- **Train vs validation** are split by **section** of the same document: no
  section appears in both.
- **Test** is a **different document** (the plan brochure), so test scores
  measure transfer to an unseen document rather than recall of training text.
- `split_stats.py` checks that chunk IDs, sections (train/val), documents
  (train+val vs test) and question texts don't overlap, and that every QA
  source chunk is in its own split. It exits non-zero if any check fails.

The QA pairs are synthetic (RAGAS + `gpt-4.1-mini`) and are a frozen copy of
`../finetuning/data`. To regenerate them from the source PDFs, see
`../finetuning/README.md` (`prepare_retriever_splits.py`, then
`generate_ragas_qa.py`). That step calls the OpenAI API; nothing in this
directory does.

## Files

| File | Purpose |
| --- | --- |
| `data/{train,validation,test}/qa_pairs.jsonl` | Question, reference answer, reference contexts, source chunk IDs |
| `data/{train,validation,test}/chunks.jsonl` | Chunks of each split's document (used as distractors) |
| `prepare_sft.py` | Builds `data/*/generator_sft.jsonl` chat examples (direct + cot) |
| `split_stats.py` | Split report + leakage checks → `results/data_splits.{md,json}` |
| `train_lora.py` | LoRA training; logs every step to `results/train_log.jsonl` |
| `plot_loss.py` | Train/validation loss + LR curves → `results/loss_curve.png` |
| `eval_generator.py` | Base vs finetuned on the test split → `results/generator_comparison.json`, `results/generator_predictions.jsonl` |
| `run_all.sh` | Runs everything above in order |
| `colab_train.ipynb` | The same pipeline as Colab cells, with upload and download steps |
| `make_colab_zip.sh` | Bundles code + data into `dist/finetuning_LLM_LORA.zip` for the notebook |
| `common.py` | Paths, base model name, JSONL helpers |
| `tests/test_pipeline.py` | Unit tests for evidence extraction, distractor mixing and CoT scoring |

## Rerun the experiment on Google Colab (GPU)

Training runs on a Colab GPU, not the Mac (see Runtime and hardware below).

1. On the Mac, bundle code + data (about 0.9 MB, no venv or models):
   ```bash
   cd /Users/dc/geha/finetuning_LLM_LORA
   ./make_colab_zip.sh
   ```
   This writes `dist/finetuning_LLM_LORA.zip`.
2. Open [`colab_train.ipynb`](colab_train.ipynb) in Colab (File → Upload
   notebook). Set Runtime → Change runtime type → **GPU**: an L4 or A100
   trains in bf16; a T4 works too, in fp32 and slower.
3. Run the cells in order. They upload the zip, install `transformers`,
   `peft`, `accelerate` and `matplotlib` (Colab already has CUDA torch), run
   the tests, build the SFT data, write the split report, train, plot the loss
   curves, and run the eval.
4. The last cell downloads `colab_results.zip` (`results/` + the adapter).
   Unzip it into this folder.

The same steps without the notebook, on any CUDA machine:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .
./run_all.sh                 # EPOCHS=2 ./run_all.sh to override
```

`--dtype auto` (the default) picks bf16 on GPUs that support it. Otherwise
training uses fp32 and the eval uses fp16. MPS and CPU always use fp32.

Quick pipeline check on CPU with a tiny random model (about 30 seconds; the
numbers are meaningless). It writes only to `/tmp/smoke`. Don't run
`eval_generator.py` with the tiny model unless you delete `results/generator_*`
afterwards, because it writes there:

```bash
.venv/bin/python train_lora.py --base-model nm-testing/tinysmokeqwen3 --device cpu \
  --limit 6 --grad-accum 2 --epochs 2 --eval-every 2 \
  --output-dir /tmp/smoke/adapter --log /tmp/smoke/train_log.jsonl
.venv/bin/python plot_loss.py --log /tmp/smoke/train_log.jsonl --output /tmp/smoke/loss.png
```

### Training log format

`results/train_log.jsonl` has one JSON object per line:

- `{"type": "config", ...}`: every CLI argument, the device, example counts,
  steps per epoch, and trainable/total parameter counts.
- `{"type": "train", "step", "epoch", "loss", "lr", "grad_norm", "elapsed_s"}`:
  one per optimizer step. `loss` is the mean over the step's 8 examples.
- `{"type": "val", "step", "epoch", "loss", "best", "elapsed_s"}`: one per
  validation pass. `best: true` means the adapter was saved at that point.

### Hyperparameters

| Flag | Default | Notes |
| --- | --- | --- |
| `--epochs` | 3 | See the epoch notes below |
| `--learning-rate` | 2e-4 | 10% linear warmup, then cosine decay to 0 |
| `--grad-accum` | 8 | Batch size 1 × 8 → effective batch 8 → **20 optimizer steps per epoch** |
| `--lora-rank` | 16 | alpha = 2 × rank |
| `--lora-dropout` | 0.05 | Raise this (e.g. 0.1) if validation loss turns up |
| `--eval-every` | 10 | Twice per epoch; each validation pass costs a few minutes on an M1 Pro |
| `--patience` | 0 (off) | Stop after N evaluations without improvement |
| `--max-length` | 3072 | Longest example is about 2.4K tokens |
| `--seed` | 42 | Vary this for repeat runs; one seed isn't enough to claim a gain |

## Notes on the number of epochs

**There isn't a hard "1–2 epoch maximum" for LoRA.** That rule of thumb comes
from instruction datasets with tens of thousands of examples. There, one epoch
is already thousands of optimizer steps, and further passes over the same data
tend to memorize it and lower quality. What actually matters is **how many
optimizer steps you take and what the held-out loss does**:

- This dataset is tiny: 156 examples ÷ 8 per step = **20 optimizer steps per
  epoch**. One epoch is only 20 updates and usually isn't enough to learn the
  CoT output format. Three epochs is 60 updates.
- Overfitting is still the main risk at this size. These safeguards are built
  in:
  1. validation loss every 10 steps on sections never seen in training;
  2. only the **best** validation checkpoint is saved, so if epoch 3 overfits,
     the earlier adapter is kept;
  3. `--patience N` for early stopping.
- How to read `loss_curve.png`: if train loss keeps falling while validation
  loss rises, the model is overfitting. Use the best checkpoint and, for the
  next run, cut epochs or the learning rate or raise dropout. If both are still
  falling at the end, more epochs may help.
- Validation loss only measures how close the model gets to the reference
  answer text. `eval_generator.py` measures what matters on an unseen document:
  answer F1, CoT format compliance, citation precision (did it cite the gold
  passage rather than a distractor?) and quote grounding (does each quoted
  sentence actually appear in the passages?).

### First attempt on the Mac (stopped; `../finetuning/train_generator.py`, per-epoch logging only)

| Epoch | Train loss | Validation loss |
| ---: | ---: | ---: |
| 0 (before training) | – | 0.626 |
| 1 | 0.517 | 0.517 |
| 2 | stopped partway | – |

The epoch-1 adapter from this run is in
`../finetuning/models/geha-dental-generator-lora`. The Colab run replaces it
and is the run to report.

## Runtime and hardware

**Why not the Mac.** On an Apple M1 Pro (32 GB) the model runs in fp32 on MPS,
because M1 has no native bf16 and fp16 LoRA training can diverge:

- epoch 1 took **56 minutes** (02:53 → 03:57 including model load and the
  first validation pass);
- epoch 2 ran **3.5 hours without finishing**. Training ran on battery,
  macOS throttled it, then hibernated the Mac at 1% charge (06:39–06:51), and
  swap filled up (15.8 of 17 GB);
- the run was stopped after 4 h 41 min.

**Colab GPU.** bf16 on an L4/A100, so the per-step cost is a small fraction
of the Mac's. `train_log.jsonl` records the real wall-clock time
(`elapsed_s`) and the GPU name (`gpu` in the config record) for the deck and
the README.

## Caveats

- 78 synthetic training QA pairs from one public document is a small,
  demo-scale dataset; results from one seed are preliminary.
- The CoT rationale is **extractive** (gold sentences that best overlap the
  reference answer), not a model-written explanation as in the FLAN paper.
- Token F1 rewards matching the RAGAS reference answers' wording, which
  finetuning optimizes directly; check the predictions file, not just the
  averages.
