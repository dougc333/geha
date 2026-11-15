# aws_ingestion

Scalable page-level ingestion of complex multipage PDFs with two pipelines and a human approval gate.

Everything here is a draft spec for review. No code yet.

- [docs/ingestion_design.md](docs/ingestion_design.md): overall design and rationale
- [docs/aws_agent_implementation_plan.md](docs/aws_agent_implementation_plan.md): staged AWS architecture, agent boundary, scaling, reliability, and demo plan
- [specs/pipelines.md](specs/pipelines.md): segmenter, pipeline 1 (tesseract + ReAct), pipeline 2 (spec first)
- [specs/page_spec.schema.json](specs/page_spec.schema.json): JSON schema for the page spec
- [specs/react_loop.md](specs/react_loop.md): tools, error count, stop conditions
- [specs/review_app.md](specs/review_app.md): React review app, approval gate, API, data model
- [specs/search_sdk.md](specs/search_sdk.md): search as code, a Python SDK for fetch, chunk, embed and retrieve
- [specs/ragas_eval.md](specs/ragas_eval.md): RAGAS end-to-end evaluation of ingestion variants
