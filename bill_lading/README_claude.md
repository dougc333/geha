# Claude (claude-opus-5-5) vs GPT and PaddleOCR-VL: bill-of-lading OCR

Claude run `claude_run_20260929T220854Z` (effort `medium`); GPT and Paddle results from `paddle_vs_gpt4o_run_20260927T192115Z` (not re-run). Same eight block images; Claude got the same instructions, cell counts and block-6 hint as GPT; same recall scoring.

| Provider | Model | Matched | Recall | Perfect blocks | OK calls | Total latency | Mean latency |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude (anthropic) | `claude-opus-5-5` | 79/79 | 100.0% | 8/8 | 8/8 | 35.172s | 4.396s |
| OpenAI | `gpt-4o` | 79/79 | 100.0% | 8/8 | 8/8 | 14.908s | 1.863s |
| Fireworks PaddleOCR-VL | `accounts/dougchang25-0sh9syiq/deployments/ohotr710` | 79/79 | 100.0% | 8/8 | 8/8 | 2.491s | 0.311s |

| Block | Claude | Claude missing | Claude s | GPT | GPT s | Paddle | Paddle s |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 100.0% | None | 4.65 | 100.0% | 1.737 | 100.0% | 0.355 |
| 2 | 100.0% | None | 7.183 | 100.0% | 3.613 | 100.0% | 0.504 |
| 3 | 100.0% | None | 2.968 | 100.0% | 1.249 | 100.0% | 0.28 |
| 4 | 100.0% | None | 2.98 | 100.0% | 1.127 | 100.0% | 0.128 |
| 5 | 100.0% | None | 3.207 | 100.0% | 1.227 | 100.0% | 0.156 |
| 6 | 100.0% | None | 5.672 | 100.0% | 2.556 | 100.0% | 0.457 |
| 7 | 100.0% | None | 2.673 | 100.0% | 1.333 | 100.0% | 0.151 |
| 8 | 100.0% | None | 5.839 | 100.0% | 2.066 | 100.0% | 0.46 |

Blocks where Claude returned a different number of entries than asked: none.
Recall only checks that each expected string appears somewhere in the block's text (lowercase, punctuation removed); it does not penalize extra text, order, or decimal-point errors.
