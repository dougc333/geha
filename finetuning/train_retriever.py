import json
from pathlib import Path

from sentence_transformers import (
    InputExample,
    SentenceTransformer,
    evaluation,
    losses,
)
from torch.utils.data import DataLoader


DATA_DIR = Path("/Users/dc/geha/finetuning/data")
TRAIN_CHUNKS_PATH = DATA_DIR / "train/chunks.jsonl"
VALIDATION_CHUNKS_PATH = DATA_DIR / "validation/chunks.jsonl"
TRAIN_PATH = DATA_DIR / "train/qa_pairs.jsonl"
VALIDATION_PATH = DATA_DIR / "validation/qa_pairs.jsonl"

OUTPUT_DIR = Path(
    "/Users/dc/geha/finetuning/models/geha-dental-retriever"
)

BASE_MODEL = "BAAI/bge-base-en-v1.5"

QUERY_PREFIX = (
    "Represent this sentence for searching relevant passages: "
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as file:
        return [json.loads(line) for line in file if line.strip()]


# Use contextualized_text when available because it gives isolated chunks
# enough document/section context to be retrieved meaningfully.
chunk_rows = load_jsonl(TRAIN_CHUNKS_PATH) + load_jsonl(
    VALIDATION_CHUNKS_PATH
)

chunks = {
    row["chunk_id"]: (
        row.get("contextualized_text")
        or row["text"]
    )
    for row in chunk_rows
}


# -------------------------
# Training pairs
# -------------------------

train_rows = load_jsonl(TRAIN_PATH)
train_examples = []

for row in train_rows:
    question = QUERY_PREFIX + row["question"]

    for chunk_id in row["source_chunk_ids"]:
        if chunk_id not in chunks:
            raise KeyError(f"Unknown training chunk: {chunk_id}")

        train_examples.append(
            InputExample(
                texts=[
                    question,
                    chunks[chunk_id],
                ]
            )
        )

train_loader = DataLoader(
    train_examples,
    batch_size=16,
    shuffle=True,
    drop_last=False,
)


# -------------------------
# Validation retrieval set
# -------------------------

validation_rows = load_jsonl(VALIDATION_PATH)

validation_queries = {}
validation_relevant_docs = {}

for row in validation_rows:
    query_id = row["id"]

    validation_queries[query_id] = (
        QUERY_PREFIX + row["question"]
    )

    validation_relevant_docs[query_id] = set(
        row["source_chunk_ids"]
    )

# All chunks remain searchable during validation.
validation_corpus = chunks

validation_evaluator = evaluation.InformationRetrievalEvaluator(
    queries=validation_queries,
    corpus=validation_corpus,
    relevant_docs=validation_relevant_docs,
    name="validation",
    accuracy_at_k=[1, 3, 5, 10],
    precision_recall_at_k=[1, 3, 5, 10],
    mrr_at_k=[10],
    ndcg_at_k=[10],
    map_at_k=[10],
    show_progress_bar=True,
)


# -------------------------
# Fine-tuning
# -------------------------

model = SentenceTransformer(BASE_MODEL)

train_loss = losses.MultipleNegativesRankingLoss(model)

model.fit(
    train_objectives=[
        (train_loader, train_loss)
    ],
    evaluator=validation_evaluator,
    epochs=3,
    warmup_steps=max(1, len(train_loader) // 10),
    evaluation_steps=max(1, len(train_loader)),
    output_path=str(OUTPUT_DIR),
    save_best_model=True,
    show_progress_bar=True,
)

print(f"Saved best encoder to: {OUTPUT_DIR}")
