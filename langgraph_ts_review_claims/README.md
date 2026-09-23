# GEHA synthetic review workspace

Local React + TypeScript + Tailwind UI with a Node TypeScript backend and LangGraph JavaScript. Not affiliated with GEHA. All six claims are fabricated. No LLM, API key, insurance decisions, or payments.

## Run

Requires Node 22.12+ (or a compatible newer release).

```sh
cd /Users/dc/geha/langgraph_web
npm ci
npm run dev
```

Open http://127.0.0.1:4317. Vite proxies `/api` to Node on port 4318. For a built, single-server demo:

```sh
npm run build
npm start
```

Then open http://127.0.0.1:4318. Do not start a second backend on the same port.

## Files

| Path | Purpose |
| --- | --- |
| `src/App.tsx` | React workspace and API calls |
| `src/components/` | ClaimList, ReviewPanel, MemoryNotice |
| `src/index.css` | Tailwind styling |
| `server/data/claims.json` | Single source of synthetic claim data; backend only |
| `server/reviews.ts` | Graph, MemorySaver, review registry and request guards |
| `server/index.ts` | Node HTTP API and built frontend serving |
| `shared/types.ts` | TypeScript types only; no data or runtime graph |
| `server/reviews.test.ts` | Workflow and concurrency tests |

## Workflow and memory

Select a claim, start a review, edit its explanation, then approve or reject with a reason. The graph runs `explain` then pauses in `human_review` using `interrupt`. A reviewer submission resumes it using `Command`. Approval releases the explanation only; it never modifies the claim status.

Each start generates a UUID thread ID on the backend. A single compiled graph and MemorySaver serve all reviews in that Node process. Refreshing the browser preserves backend reviews; select one from Session reviews to reopen it. Restarting Node deletes ALL review records and checkpoints; only the source claim JSON remains. This is not durable storage or a tamper-proof audit trail.

API: GET `/api/claims`, `/api/reviews`, `/api/reviews/:id`, `/api/reviews/:id/history`, `/api/health`; POST `/api/reviews` with `{claimId, requestId}`; POST `/api/reviews/:id/decision` with `{requestId, decision: {action, reason, text}}`. Request IDs must be UUIDs. Reusing a completed request ID with identical input returns its result; conflicting input is rejected. Simultaneous reviews of one case return a conflict to the losing request. The UI generates request IDs but does not automatically retry failed submissions.

## Limits and checks

Local demo only: loopback binding, origin checks, JSON validation, request size limit, 200-start memory cap, and per-case in-process concurrency guard. No authentication or multi-process coordination. Every local user can view every synthetic case. Do not expose publicly or add patient/member data. A production deployment needs identity/ownership enforcement, durable checkpoints, atomic cross-process review transitions and retention controls.

```sh
npm test
npm run build
```

Tests cover pause/checkpoints, approval, rejection, idempotent starts and completed decisions, concurrent opposing decisions, invalid requests, and fresh-service memory reset.
