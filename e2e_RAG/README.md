# e2e_RAG

This project includes PDF loading, chunking, Chroma retrieval, optional query
expansion and reranking, answer generation, and an optional offline Ragas
evaluation command.

## Install

```bash
cd /Users/dc/geha/e2e_RAG
uv pip install -r requirements.txt
```

Set `OPENAI_API_KEY` in the environment before using OpenAI generation or
evaluation models.

## Run the Ragas evaluation

Copy `evals/questions.example.jsonl` and replace its sample content with
approved questions and reference answers. Each JSONL record requires
`user_input` and `reference`; `reference_contexts` is optional.

```bash
cd /Users/dc/geha/e2e_RAG/src
python evaluate_ragas.py \
  --pdf ../data/2306.02707.pdf \
  --dataset ../evals/questions.example.jsonl \
  --output ../evals/results.json \
  --reranker-model none
```

The report contains per-question and mean scores for:

- `faithfulness`: whether claims in the answer are supported by retrieved text.
- `answer_relevancy`: whether the answer addresses the question.
- `context_precision`: whether useful passages are ranked ahead of noise.
- `context_recall`: whether the retrieved passages contain the reference facts.

Ragas is kept out of the normal CLI and Streamlit answer path. Evaluation makes
additional evaluator-model and embedding API calls, so run it deliberately on
a versioned test set rather than on every user request.

The project pins Ragas 0.4.3. That release imports a LangChain Vertex AI
compatibility module that modern `langchain-community` removed, so the local
adapter supplies the optional import only for Ragas. This evaluation uses
OpenAI and does not install or invoke Vertex AI.

## Test

```bash
cd /Users/dc/geha/e2e_RAG/src
python -m unittest test_class_refactor test_ragas_evaluator
```
