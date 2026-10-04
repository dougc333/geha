# Benefits chatbot on Vercel

The dental + medical state machine from `../src/benefits_bot.py` as a Vercel app: a
static chat page (`public/index.html`) and one Python function (`api/chat.py`,
`POST /api/chat`). No model, API key or database.

## How it differs from the Streamlit app

| | Streamlit (`../src/benefits_chat_app.py`) | Vercel |
|---|---|---|
| UI | Streamlit chat | `public/index.html`, plain HTML and JS |
| Conversation state | kept in server memory per thread | sent by the page with every message (`BenefitsBot.step`), cleaned by `clean_state` before use |
| Tables and brochure corpus | parsed from the PDFs/Markdown at start-up | `tables.json`, exported by `scripts/build.py` |
| Runtime dependencies | PyMuPDF, Streamlit, LangGraph | LangGraph only |

`benefits/` holds unchanged copies of the bot modules from `../src`; the function imports
them from there. A test fails if they or `tables.json` go stale.

The medical state machine also contains a local BM25 retrieval node over the 132-page
2026 Elevate and Elevate Plus brochure. `scripts/build.py` ingests the page-numbered
Docling Markdown from `downloads/medical/fehb/single_pages/` into 336 page-cited chunks
in `tables.json`. Known premiums, deductibles, and benefit topics continue to use the
deterministic structured tables; other medical questions route to the brochure corpus.
No vector database or model call is required at runtime.

## Build, run, test

```bash
cd /Users/dc/geha/e2e_RAG/benefits_vercel
../../.venv/bin/python scripts/build.py           # after changing ../src or the PDFs
../../.venv/bin/python local_server.py 3000       # http://localhost:3000, no Vercel CLI needed
../../.venv/bin/python -m unittest test_benefits_vercel
```

The tests check that the module copies and `tables.json` match `../src` and the PDFs,
that the function runs with PyMuPDF blocked and no PDFs present, a full conversation
through the state round trip ($1,086.93 monthly total), that all 52 conversations in
`../evals/benefits_conversations.jsonl` get exactly the same replies as the stateful
bot, that the screenshot-derived benefit queries in `../evals/benefits_questions.jsonl`
contain every expected phrase and no rejected phrase, that bad requests are rejected
and untrusted state is cleaned, and the page and API over HTTP through `local_server.py`.

Each line of `benefits_questions.jsonl` is one independent query:

```json
{"id":"hearing-discount","category":"member discounts","query":"What hearing aid discount is included with my dental plan?","expect_in_reply":["30%-60% off TruHearing"],"reject_in_reply":["not found"]}
```

`reject_in_reply` is optional. Add a new JSON object on its own line to extend the
benefit regression set without changing Python test code.

## Deploy

1. Create a Vercel project with **Root Directory** `e2e_RAG/benefits_vercel`. No
   environment variables are needed.
2. Vercel installs `requirements.txt` (`langgraph`), serves `public/` as static files and
   deploys `api/chat.py` with `tables.json` and `benefits/` bundled (`vercel.json`).
3. Or from this folder with the Vercel CLI: `vercel` (preview) then `vercel --prod`.

The page states that it is a demo, not affiliated with G.E.H.A. A deployment is public;
check the rates against the official sources before sharing it, and re-run
`scripts/build.py` when the 2027 PDFs come out.
