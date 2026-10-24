import type { DocumentRecord } from "./store/ingestion";

export interface PageArtifact {
  page: number;
  source_image: string | null;
  docling_markdown: string | null;
  deepseek_markdown: string | null;
  llamaparse_markdown: string | null;
  ocr_engine: OcrEngine;
  ocr_markdown: string | null;
  markdown_source: OcrEngine | "docling";
  issues: string[];
}

export interface PageManifest {
  schema_version: string;
  pages: PageArtifact[];
  summary: {
    page_count: number;
    deepseek_pages: number;
    llamaparse_pages: number;
    ocr_pages: number;
    ocr_engine: OcrEngine;
    issue_count: number;
  };
}

export interface IngestionRun {
  run_id: string;
  created_at: string | null;
  completed_at: string | null;
  ocr_engine: OcrEngine | "unknown";
  status: "complete" | "incomplete";
  page_count: number;
  ocr_pages: number;
  issue_count: number;
  is_current: boolean;
}

export interface ClusterRecord {
  id: string;
  label: string;
  document_count: number;
  description: string;
  destination: string;
}

export interface RouterEvent {
  stage: "received" | "validating_jsonl" | "classifying" | "routed";
  status: "running" | "complete" | "failed";
  detail?: string;
}

export interface QueryRoute {
  line: number;
  query: string;
  cluster: string;
  confidence: number;
  method: "jev" | "deterministic_fallback" | "research_finding_guardrail";
  signals: string[];
  score: number;
  probabilities: Record<string, number>;
  destination: string;
}

export interface QueryRouterResponse {
  run_id: string;
  created_at: string;
  input_jsonl: string;
  status: "routed";
  router: {
    name: string;
    provider: string;
    jev_available: boolean;
    sdk_installed: boolean;
    key_configured: boolean;
    mode: "jev" | "deterministic_fallback";
    fallback_reason?: string;
  };
  events: RouterEvent[];
  clusters: ClusterRecord[];
  routes: QueryRoute[];
}

export interface QueryExample {
  id: string;
  cluster: string;
  user_input: string;
  source_documents: string[];
}

export interface ContextualPageStatus {
  page: number;
  chunk_id: string;
  source_markdown: string;
  status: "pending" | "processing" | "complete";
  contextualized_at: string | null;
  prompt_cache: {
    input_tokens?: number;
    output_tokens?: number;
    cache_creation_input_tokens?: number;
    cache_read_input_tokens?: number;
  };
}

export interface ContextualRetrievalStatus {
  schema_version: string;
  status: "idle" | "running" | "complete" | "failed";
  document_id: string;
  filename: string;
  model: string;
  prompt_version: string;
  total_pages: number;
  completed_pages: number;
  current_page: number | null;
  error: string | null;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  pages: ContextualPageStatus[];
  updated_at: string | null;
  storage_strategy?: "whole_document";
  source_page_count?: number;
  retrieval_units?: number;
  source_path?: string;
  source_uri?: string;
  context_artifact?: string;
  vector_database?: string;
  embedding_model?: string;
  embedding_dimensions?: number;
}

export interface ContextualPageResult {
  page: number;
  chunk_id: string;
  text: string;
  source_markdown: string;
  retrieval_context: string;
  contextual_retrieval_text: string;
  contextualized_at: string;
  prompt_cache: ContextualPageStatus["prompt_cache"];
}

export interface ContextualJudgePageStatus {
  page: number;
  status: "pending" | "processing" | "complete";
  verdict: "pass" | "review" | "fail" | null;
  source_integrity: "clean" | "suspect" | "corrupt" | null;
  context_grounding: "grounded" | "partially_grounded" | "unsupported" | null;
  source_issues: string[];
  context_issues: string[];
  rationale: string | null;
  confidence: number | null;
}

export interface ContextualJudgeStatus {
  schema_version: string;
  status: "idle" | "running" | "complete" | "failed";
  document_id: string;
  model: string;
  prompt_version: string;
  total_pages: number;
  completed_pages: number;
  current_page: number | null;
  error: string | null;
  counts: { pass: number; review: number; fail: number };
  pages: ContextualJudgePageStatus[];
  updated_at: string | null;
}

export interface ContextualJudgment extends ContextualJudgePageStatus {
  verdict: "pass" | "review" | "fail";
  source_integrity: "clean" | "suspect" | "corrupt";
  context_grounding: "grounded" | "partially_grounded" | "unsupported";
  rationale: string;
  confidence: number;
  chunk_id: string;
  source_sha256: string;
  context_sha256: string;
  judge_model: string;
  judge_prompt_version: string;
  judged_at: string;
}

export interface FormVectorRecord {
  document_id: string;
  chunk_id: string;
  filename: string;
  source_path: string;
  source_uri: string;
  retrieval_context: string;
  embedding_model: string;
  embedding_dimensions: number;
  document_sha256: string;
  updated_at: string;
}

export interface RuntimeIndexRecord {
  document_id: string;
  chunk_id: string;
  filename: string;
  cluster: string | null;
  pages: number[];
  text: string;
  retrieval_context: string;
  contextual_retrieval_text: string;
  embedding_model: string;
  embedding_dimensions: number;
  review_status: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const ingestionApi = {
  list: () => request<DocumentRecord[]>("/api/documents"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<DocumentRecord[]>("/api/documents", { method: "POST", body: form });
  },
  runNext: (ocrEngine: OcrEngine = "deepseek") => request<{ submitted: number; documentId: string | null }>("/api/jobs/run-next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ocr_engine: ocrEngine }),
  }),
  runDocument: (id: string, ocrEngine: OcrEngine = "deepseek") => request<{ submitted: boolean; documentId: string }>(`/api/documents/${id}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ocr_engine: ocrEngine }),
  }),
  retry: (id: string) => request<{ submitted: boolean }>(`/api/documents/${id}/retry`, { method: "POST" }),
  runs: (id: string) => request<IngestionRun[]>(`/api/documents/${id}/runs`),
  pageManifest: (id: string, path: string) => request<PageManifest>(`/api/documents/${id}/artifacts/${path}`),
  runPageManifest: (id: string, runId: string) => request<PageManifest>(`/api/documents/${id}/runs/${runId}/page-manifest`),
  runPageSource: (id: string, runId: string, page: number) => `/api/documents/${id}/runs/${runId}/pages/${page}/source`,
  artifactText: async (id: string, path: string) => {
    const response = await fetch(`/api/documents/${id}/artifacts/${path}`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.text();
  },
  runArtifactText: async (id: string, runId: string, path: string) => {
    const response = await fetch(`/api/documents/${id}/runs/${runId}/artifacts/${path}`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.text();
  },
  clusters: () => request<ClusterRecord[]>("/api/clusters"),
  queryExamples: (limit = 30) => request<QueryExample[]>(`/api/query-examples?limit=${Math.min(Math.max(limit, 1), 30)}`),
  routerRuns: () => request<QueryRouterResponse[]>("/api/query-router/runs"),
  routeJsonl: (jsonl: string) => request<QueryRouterResponse>("/api/query-router", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonl }),
  }),
  contextualStatus: (id: string) => request<ContextualRetrievalStatus>(`/api/documents/${id}/contextual-retrieval`),
  runContextual: (id: string) => request<{ submitted: boolean; documentId: string }>(`/api/documents/${id}/contextual-retrieval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_cost: true }),
  }),
  contextualPage: (id: string, page: number) => request<ContextualPageResult>(`/api/documents/${id}/contextual-retrieval/pages/${page}`),
  contextualPageSource: async (id: string, page: number) => {
    const response = await fetch(`/api/documents/${id}/contextual-retrieval/pages/${page}/source`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.text();
  },
  contextualJudgeStatus: (id: string) => request<ContextualJudgeStatus>(`/api/documents/${id}/contextual-retrieval/judge`),
  runContextualJudge: (id: string) => request<{ submitted: boolean; documentId: string }>(`/api/documents/${id}/contextual-retrieval/judge/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_cost: true }),
  }),
  contextualJudgment: (id: string, page: number) => request<ContextualJudgment>(`/api/documents/${id}/contextual-retrieval/judge/pages/${page}`),
  formVectorRecords: () => request<FormVectorRecord[]>("/api/vector-db/forms"),
  runtimeIndexes: () => request<RuntimeIndexRecord[]>("/api/runtime/indexes"),
};

export type OcrEngine = "deepseek" | "llamaparse";
