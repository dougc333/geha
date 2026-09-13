# Reliability tests

Implemented integration/regression suite for the local LangGraph demo. These tests are separate from the ordinary unit tests and use only disposable synthetic inputs and SQLite databases.

## Run

```bash
cd /Users/dc/geha/langgraph_demo
uv run python -m unittest discover -s reliability_tests -p 'test_*.py' -v
```

Current result (2026-09-11): **8 tests: 5 pass, 3 fail** on LangGraph 1.2.11 and langgraph-checkpoint-sqlite 3.1.1. Failures deliberately assert desired guarantees and are not marked skipped or expected failures. The command exits nonzero until the gaps are fixed. Production code was not changed to make tests pass.

| Test area | What is exercised | Observed result |
| --- | --- | --- |
| Crash after interrupt commit | Kill child with SQLite connection still open; inspect in fresh process and resume | Pass |
| Crash before resume checkpoint put | Test-only hook signals before checkpoint persistence; kill worker; recover pending work in another process | Pass |
| Crash after completion, before client acknowledgement | Kill worker after commit; reject repeat review without altering saved result | Pass |
| Concurrent reviews | Two child processes both read pending state, then attempt opposing decisions | **Fail: both accepted** |
| Sequential duplicate | Repeated approval or rejection after completion creates no new checkpoints | Pass |
| Persistent request IDs | Require `request_id`, replay the original response after reopen, and reject mismatched payload reuse | **Fail: API has no request_id parameter** |
| Upstream node-exception control | Retry a transient node failure with SQLite | Pass |
| Upstream router-exception recovery | Retry a transient conditional-router failure and reach the downstream node | **Fail: downstream skipped** |

## Files

- `support.py`: synthetic fixtures, spawn-based workers, pipe handshakes, cleanup, and SQLite integrity checks.
- `test_crash_recovery.py`: three force-kill scenarios.
- `test_concurrent_reviews.py`: synchronized cross-process review race.
- `test_idempotency.py`: sequential-duplicate protection and persistent idempotency contract.
- `test_upstream_regressions.py`: independently adapted behavioral reproduction of [LangGraph issue #8834](https://github.com/langchain-ai/langgraph/issues/8834), with a passing node-failure control and versions in failure output.

The idempotency contract currently stops at the missing-parameter assertion; its replay/conflicting-payload checks execute only after the API exists. It is not evidence that persistent deduplication works. Concurrent same-request-ID testing is also still dependent on implementing that API. The tested router failure is a minimal graph, not a claim that ordinary authorization currently throws this error.

## Safety and boundaries

- Never reads or modifies the live `data/checkpoints.sqlite` or source claim files. Every test constructs a temporary input tree and verifies its inputs remain unchanged.
- Child processes are created with Python's spawn method. Kill operations target only process objects created by the test, never discovered servers or arbitrary PIDs.
- Pipes coordinate exact milestones; there are no timing sleeps. Each wait is bounded at 20 seconds, followed by bounded join/cleanup. All workers are cleaned up on failure.
- The pre-commit test patches `SqliteSaver.put` on that child's saver instance only. It models a crash before a checkpoint write, not a power failure in the middle of a storage-device write. Pending writes can already be durable, so recovery continues persisted work before injecting another decision.
- These tests exercise process death, not machine power loss, disk-full errors, network failures, or external-payment exactly-once guarantees.
- No network/API access or LLM is needed to run the tests. The upstream report was inspected during authoring; no downloaded code is executed.

Next implementation work is cross-process review coordination and persistent idempotency. The upstream recovery failure requires a tested runtime fix/upgrade or an application-level strategy. Do not weaken the checks to manufacture a green suite.
