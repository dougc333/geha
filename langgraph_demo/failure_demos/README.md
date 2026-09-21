# LangGraph failure laboratory

These standalone programs use disposable synthetic inputs and temporary SQLite databases. They do not modify the normal `data/checkpoints.sqlite` file.

```bash
cd /Users/dc/geha/langgraph_demo

uv run python -m failure_demos.demo_failure_restart
uv run python -m failure_demos.demo_failure_concurrency

uv run python -m failure_demos.demo_failure_upstream transient
uv run python -m failure_demos.demo_failure_upstream permanent
uv run python -m failure_demos.demo_failure_upstream timeout
uv run python -m failure_demos.demo_failure_upstream invalid-output

# Requires the local Langfuse .env configuration.
uv run python -m failure_demos.demo_failure_distributed_trace --workers 4

# Opt-in integration assertion against the running local Langfuse stack.
RUN_LANGFUSE_INTEGRATION_TESTS=1 \
  uv run python -m unittest -v test_failure_distributed_trace
```

The concurrency program forces two processes to observe the same pending review
before either proceeds. The local SQLite implementation uses a sibling-file lock,
rechecks saved state inside that lock, and accepts exactly one opposing decision;
the other is rejected. A distributed deployment must replace this local control
with a PostgreSQL transaction/advisory lock or transactional compare-and-set.

The restart program kills only the worker process it created, after the interrupt checkpoint is durable. A new process reopens the database and resumes the pending review.

The distributed tracing program creates a parent observation and sends its 32-character W3C trace ID and 16-character parent span ID to independent spawned processes. Every process runs a small LangGraph and attaches its own child observation to that parent. Search for the printed trace ID under **Tracing** in `http://localhost:3000`.
