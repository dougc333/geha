# GEHA project catalog

This catalog lists every top-level directory in the repository. Each summary is
intentionally shorter than 2,000 characters. Directories that contain multiple
runnable projects have a second-level inventory after the main list.

## Top-level directories

### [`PDF_processing`](PDF_processing/README.md)

Research workflows for extracting dense forms by dividing pages into semantic
regions, applying literal OCR, validating typed fields and reconstructing
inspectable HTML. The directory contains the `blocking_demo` page-segmentation
experiment and the `bill_lading` eight-block OCR benchmark; it is research code,
not a general PDF service or HIPAA-ready pipeline.

### [`advanced_rag`](advanced_rag/README.md)

An AWS-oriented RAG experiment covering query routing, retrieval evaluation and
deployment architecture. Its notes focus on realistic underspecified queries,
the operational cost of a continuously deployed Fargate/ALB stack and the
trade-offs involved in rebuilding or tearing down cloud resources.

### [`agent_permissions`](agent_permissions/README.md)

A fail-closed authorization layer for LangChain tool-calling agents.
`PermissionMiddleware` applies ordered `ALLOW`, `DENY` and `ASK` rules, supports
interactive approval, inspects command arguments and writes audit events. It is
application-level policy enforcement rather than an OS sandbox or firewall.

### [`agentic_file_search`](agentic_file_search/)

An empty placeholder reserved for a future agentic file-search project. It has
no implementation or README yet and should not be treated as an active system.

### [`agentic_search`](agentic_search/README.md)

Two bounded search workflows over scientific papers: a fixed corrective-RAG
LangGraph loop inspired by CRAG/Self-RAG and a model-directed ReAct loop. The
corrective workflow retrieves, reranks, grades evidence, rewrites weak queries,
checks support and can use either a local Chroma corpus or the deployed
`aws_rag` retrieval service.

### [`agentic_search_corpus`](agentic_search_corpus/README.md)

A dental-policy adaptation of the agentic search code. It indexes canonical
page-level Markdown rather than duplicate PDF/HTML siblings, supports BM25,
vector and hybrid retrieval, and preserves page metadata for citations and
agentic answers.

### [`autogen-demo`](autogen-demo/)

A local AutoGen Studio workspace containing Studio configuration, database and
environment artifacts. It currently has no repository-level implementation
README, so it should be treated as a development workspace rather than a
documented reusable application.

### [`aws_context`](aws_context/)

An empty placeholder reserved for future AWS context-management work. It has no
implementation or README yet.

### [`aws_rag`](aws_rag/README.md)

A serverless multimodal RAG platform over 203 public machine-learning papers.
It combines BM25 and pgvector retrieval with reciprocal-rank fusion, Bedrock
reranking, cited generation, Langfuse tracing and Docling-derived text, table
and figure chunks. It also exposes retrieval without generation for other
bounded agent workflows.

### [`bounding_box`](bounding_box/README.md)

A PDF figure-region annotation and reconstruction workspace for charts, tables,
logos, photos, diagrams and other non-running-text regions. It includes manual
annotation, a vision-agent annotation path, evidence-backed reconstruction
prompts and a React review application; newer spec-file workflows supersede
some of the original bounding-box approach.

### [`browser_gym`](browser_gym/README.md)

An experiment in allowing an LLM to control a browser. Each run writes a
durable JSONL trajectory containing observations, prompts, actions, rewards,
termination state and environment details so partial and completed runs can be
inspected locally.

### [`chunking_benchmarks_RAG`](chunking_benchmarks_RAG/README.md)

A table-aware coverage-policy RAG system and benchmark suite. It retrieves
child rows but assembles parent tables and attached context for the model,
provides deterministic billing-code lookup and tracks eleven evaluation case
families covering exact codes, indications, secondary conditions and combined
application behavior.

### [`collections`](collections/)

A React/Vite dashboard with a small Python API for reconciling GEHA's live
public-document catalog with manifests, downloaded PDFs, extraction runs and
review/promotion state. It displays provenance, hashes, pipeline status and
documents needing attention; the current interface is read-only.

### [`context_assembly_benchmarks`](context_assembly_benchmarks/README.md)

A controlled benchmark for a specific RAG failure mode: retrieval finds the
right row but the assembled prompt omits its table, qualifier, note or
exception. It holds child-row ranking constant while comparing flat rows,
parent tables and parent tables with attached explanatory text.

### [`context_compiler`](context_compiler/README.md)

A demonstration comparing a plain agent that resends full history with agents
that compile each prompt from a complete event log. It measures cumulative
cost, recall and prompt-cache behavior to show when selective context saves
tokens and when breaking a cached prefix makes it more expensive.

### [`contextual_retrieval_dashboard`](contextual_retrieval_dashboard/README.md)

A React workbench for generating and inspecting contextual retrieval over the
canonical document corpus. It keeps source evidence unchanged for citations
while attaching short document-aware descriptions used by BM25 or embedding
indexes, and supports both policy text and saved visual figures.

### [`crawl_dir`](crawl_dir/README.md)

The canonical boundary for public source PDFs and extracted artifacts. It
separates original `raw` files, immutable candidate `runs`, reviewed/promoted
outputs and verification data; shared consumers resolve paths through
`crawl_dir.src.consumer_paths`. It also contains download/manifest tooling, a
corpus statistics app and the confirmation-gated `geha-ingestion` MCP server.

### [`docs`](docs/)

Shared visual and presentation assets for the repository: architecture
diagrams, RAG pattern illustrations, slide decks, reports, animations and small
utilities that generate presentation graphics. This is a support directory,
not a separately deployed application.

### [`document_ingestion_workflow`](document_ingestion_workflow/README.md)

An auditable ingestion demonstration that routes curated public PDFs through
the appropriate extraction workflow and streams tool decisions and processing
events to a React interface. The UI shows authoritative source pages beside
generated semantic HTML and visual corrections while Python controls the
bounded workflow and writes immutable candidate runs.

### [`dspy_dental_chatbot`](dspy_dental_chatbot/README.md)

A Streamlit application containing two evidence-grounded dental assistants.
Enrollment uses a deterministic state machine for eligibility, rate codes,
plans and premiums, while policy Q&A combines local retrieval, structured
benefit data, DSPy generation, citations and safety checks. It also includes a
retrieval-comparison workspace and evaluation suites.

### [`duplicate_chunks`](duplicate_chunks/README.md)

A React/Vite/TypeScript application for finding, measuring and reviewing
duplicate chunks in the canonical corpus. It separates corpus analysis from UI
serving and uses validated data files plus shared client state to make overlap
and duplication inspectable.

### [`e2e_RAG`](e2e_RAG/README.md)

A local end-to-end RAG baseline covering PDF loading, chunking, Chroma
retrieval, optional query expansion and reranking, answer generation and an
offline Ragas evaluation command. It also includes a retrieval-comparison UI
and an older Vercel application variant.

### [`e2e_bm25vector`](e2e_bm25vector/README.md)

A deployable Vercel/Neon retrieval experiment comparing true Okapi BM25,
pgvector similarity and reciprocal-rank-fusion hybrid search. Optional stages
add LLM reranking and cited generation, while the UI exposes latency and raw
evidence for each stage.

### [`finetuning`](finetuning/README.md)

A small demonstration of contrastively fine-tuning `BAAI/bge-base-en-v1.5` for
dental-policy retrieval with section-disjoint train/validation data and a
separate held-out brochure. The README explicitly notes that the two-document
dataset is too small for production conclusions.

### [`finetuning_LLM_LORA`](finetuning_LLM_LORA/README.md)

The generator half of the dental RAG fine-tuning experiments. It applies LoRA
to a small Qwen instruction model using assistant-only loss, mixes direct and
chain-of-thought-style examples, and trains on gold passages plus shuffled
distractors so the generator learns to ignore irrelevant retrieval results.

### [`fullstack`](fullstack/README.md)

Architecture notes for secure-by-design agentic applications and policy
management. The work explores how one high-level security requirement maps
across organization policy, IAM boundaries, VPC controls, model access, MCP
servers, drift detection and other interacting cloud control planes.

### [`geha_processing`](geha_processing/README.md)

The repository-wide shared Python library. It centralizes deterministic I/O,
PDF conversion and splitting, table repair, contextual-retrieval prompts,
reusable RAG services, benchmark utilities and FHIR fraud analytics while
leaving provider adapters, orchestration and UIs in their owning projects.

### [`geha_tau2`](geha_tau2/README.md)

A `tau2`-bench customer-service domain for synthetic GEHA dental member calls.
An LLM agent uses read and write tools against a sandbox database, another LLM
plays the member, and grading considers both the final database state and what
the agent told the member. Public plan data supplies policy facts; all members,
enrollments and claims are synthetic.

### [`hapi`](hapi/README.md)

A collection of local FHIR and healthcare-agent projects sharing a Dockerized
HAPI FHIR R4 server, PostgreSQL, deterministic Synthea records and a read-only
MCP bridge. It includes direct and LangChain FHIR agents, a pharmacy agent,
claim analytics, a fraud investigation UI and a teacher-guided optimization
experiment. It is a synthetic-data research lab, not one monolithic app.

### [`hybrid_docling_chunking`](hybrid_docling_chunking/README.md)

An isolated experiment measuring full-document Docling `HybridChunker` output
before any contextual-retrieval model is called. It records chunk counts and
JSONL artifacts without invoking an LLM, embedding service or AWS resource, so
chunking changes can be evaluated without mutating ingestion runs.

### [`learn_then_compile`](learn_then_compile/README.md)

A minimal offline example of learning an execution pattern from graded agent
runs and compiling the successful behavior into deterministic code. Clear
cases use the cheaper workflow, while a router sends uncertain cases back to
the agent; it mirrors the larger fraud-investigation workflow mode.

### [`mcp_benefits_server`](mcp_benefits_server/README.md)

A deterministic MCP server for dental plan data and coverage-policy search.
Each tool declares its deployment tier, data class, access pattern, owner and
version; deployments expose only promoted tools, audit logs hash PHI-like
arguments, and CI rejects tools that claim a tier whose requirements they do
not meet.

### [`production_controls`](production_controls/README.md)

AWS-ready controls and services that move document-processing state out of a
developer laptop. The initial project is an S3-backed collection downloader
with a backend and frontend for controlled acquisition and storage of public
documents.

### [`scripts`](scripts/)

Narration and demonstration scripts for the main repository projects,
including AWS RAG, ingestion and bounding boxes, contextual retrieval, agentic
search, the MCP benefits server, advanced RAG and the HAPI FHIR agent lab. This
is supporting material rather than executable product code.

## Nested project collections

### `PDF_processing`

- [`blocking_demo`](PDF_processing/blocking_demo/README.md): divides a dense
  page into smaller regions before vision OCR and uses bounded visual correction
  to improve reconstruction.
- [`bill_lading`](PDF_processing/bill_lading/README.md): evaluates multiple OCR
  systems against a typed eight-block bill-of-lading schema and saved runs.

### `bounding_box`

- [`figure_bbox_app`](bounding_box/figure_bbox_app/README.md): the React user
  interface for drawing, reviewing and exporting figure-region annotations.

### `crawl_dir`

- [`stats_app`](crawl_dir/stats_app/): a React application for inspecting corpus
  and extraction statistics.
- [`src/ingestion_mcp.py`](crawl_dir/src/ingestion_mcp.py): confirmation-gated
  MCP tools for previewing, downloading and ingesting manifest-pinned public
  documents.

### `e2e_RAG`

- [`vercel_app`](e2e_RAG/vercel_app/README.md): an earlier deployable web variant
  retained alongside the local end-to-end baseline.

### `hapi`

- [FHIR development stack](hapi/README.md): HAPI FHIR R4, PostgreSQL, shared
  configuration and read-only MCP access.
- [`synthea`](hapi/synthea/): deterministic synthetic patient generation and
  FHIR transaction bundles.
- [`mcp_agent_demo.py`](hapi/mcp_agent_demo.py): minimal Anthropic MCP tool-use
  loop over FHIR reads.
- [`langgraph_agent.py`](hapi/langgraph_agent.py): LangChain FHIR agent with
  permission middleware.
- [`pharmacy_agent.py`](hapi/pharmacy_agent.py): joins FHIR medication records
  with RxNorm and openFDA.
- [`claim_insights`](hapi/claim_insights/): seeds and detects known claimant,
  provider and comorbidity signals.
- [`fraud`](hapi/fraud/README.md): traced fraud investigator with agent,
  compiled-workflow and routed modes.
- [`self-improving-agents`](hapi/self-improving-agents/README.md): teacher-guided
  prompt and tool optimization with held-out grading and human approval.

### `production_controls`

- [`collection_downloader`](production_controls/collection_downloader/README.md):
  S3-backed backend/frontend service for controlled public-document collection.

## Project names at a glance

1. PDF Processing Experiments
2. AWS Advanced RAG
3. Agent Permissions
4. Agentic File Search (placeholder)
5. Agentic RAG Search
6. Dental Agentic Search Corpus
7. AutoGen Studio Demo Workspace
8. AWS Context (placeholder)
9. AWS Multimodal RAG
10. PDF Figure Bounding-Box Workflow
11. Browser Gym
12. Table-Aware Coverage Policy RAG
13. Collection Inventory
14. Context Assembly Benchmarks
15. Context Compiler
16. Contextual Retrieval Workbench
17. GEHA Document Processing Corpus
18. Shared Documentation and Presentations
19. Document Ingestion Workflow
20. DSPy Dental Chatbot
21. Duplicate Chunks
22. End-to-End RAG
23. BM25/Vector Retrieval Comparison
24. GEHA Retriever Fine-Tuning
25. GEHA Generator LoRA Fine-Tuning
26. Agentic Full-Stack Architecture
27. GEHA Processing Library
28. GEHA Dental `tau2` Benchmark
29. Synthetic FHIR and Healthcare-Agent Lab
30. Hybrid Docling Chunking
31. Learn Then Compile
32. GEHA Benefits MCP Server
33. GEHA Production Controls
34. Demonstration Scripts
