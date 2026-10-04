# agentic_search retrieval benchmark

Embedding model: `BAAI/bge-large-en-v1.5`

| Questions | Recall@5 | MRR@10 | nDCG@10 | Median latency | p95 latency |
|---:|---:|---:|---:|---:|---:|
| 14 | 1.0000 | 1.0000 | 1.0000 | 25.0 ms | 99.3 ms |

| Query | Gold source | First relevant rank | Latency |
|---|---|---:|---:|
| What architecture dispenses with recurrence and convolutions and relies entirely on attention? | 1706.03762v7.pdf | 1 | 42.9 ms |
| Which paper introduced the Transformer architecture using multi-head self-attention? | 1706.03762v7.pdf | 1 | 24.6 ms |
| Which 13-billion-parameter model learns explanation traces from GPT-4? | 2306.02707.pdf | 1 | 25.4 ms |
| What model uses progressive learning from complex explanation traces of GPT-4? | 2306.02707.pdf | 1 | 25.7 ms |
| Which framework retrieves, generates, and critiques through self-reflection using reflection tokens? | 2310.11511v1.pdf | 1 | 25.0 ms |
| What method trains a language model to adaptively retrieve passages and critique its own generations? | 2310.11511v1.pdf | 1 | 24.5 ms |
| Which method uses a lightweight retrieval evaluator to trigger corrective actions for retrieved documents? | 2401.15884v3.pdf | 1 | 24.5 ms |
| What retrieval-augmented generation approach performs web searches when retrieved documents are incorrect? | 2401.15884v3.pdf | 1 | 24.9 ms |
| Which 671-billion-parameter mixture-of-experts model activates 37 billion parameters per token and uses MLA? | 2412.19437v2.pdf | 1 | 99.3 ms |
| What model uses an auxiliary-loss-free load-balancing strategy and a multi-token prediction objective? | 2412.19437v2.pdf | 1 | 25.0 ms |
| Which 2.8-trillion-parameter mixture-of-experts model has 104 billion activated parameters and a one-million-token context window? | 2607.24653v2.pdf | 1 | 26.5 ms |
| What model introduces Stable LatentMoE and uses Kimi Delta Attention? | 2607.24653v2.pdf | 1 | 24.6 ms |
| Which architecture combines hybrid sparse attention with two-level KV sharing? | 2609.26368v1.pdf | 1 | 24.1 ms |
| What method introduces KV Bridging with a YOCO-style self-decoder and cross-decoder? | 2609.26368v1.pdf | 1 | 26.0 ms |
