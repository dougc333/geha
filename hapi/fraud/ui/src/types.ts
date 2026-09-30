export type Source = "fhir-mcp" | "analytics";

export interface ToolInfo {
  name: string;
  source: Source;
  description: string;
}

export interface Finding {
  provider: string;
  name?: string;
  scheme: string;
  claims?: number;
  amount_at_risk?: number;
  evidence?: string;
  confidence?: string;
}

export interface ScoreResult {
  level?: number;
  guilty: number;
  found: number;
  schemes_total: number;
  schemes_described: number;
  false_positive_providers: number;
  false_positives: { provider: string; name: string; scheme: string; confidence?: string }[];
  providers: { provider: string; name: string; found: boolean; schemes: Record<string, boolean> }[];
}

export type TraceEvent = { t: number } & (
  | { type: "run_start"; question: string; model: string; tools: ToolInfo[] }
  | { type: "thinking"; step: number; text: string }
  | { type: "text"; step: number; text: string }
  | { type: "tool_call"; step: number; call_id: string; name: string; source: Source; args: Record<string, unknown> }
  | { type: "tool_result"; step: number; call_id: string; name: string; source: Source; ms: number;
      is_error: boolean; size: number; preview: string; truncated?: boolean }
  | { type: "final"; text: string; findings: Finding[] | null }
  | { type: "done"; tool_calls: number; model_steps: number; seconds: number;
      usage: { input_tokens: number; output_tokens: number } }
  | { type: "error"; message: string; detail?: string }
  | ({ type: "score" } & ScoreResult)
);

export interface SavedRun {
  run_id: string;
  started?: string;
  question: string;
  status: "done" | "error" | "incomplete";
  error?: string | null;
  model_steps?: number;
  tool_calls?: number;
  seconds?: number;
  input_tokens?: number;
  output_tokens?: number;
  findings?: number;
  level?: number | null;
  level_title?: string | null;
  agent?: string | null;
  found?: number | null;
  guilty?: number | null;
  false_positive_providers?: number | null;
}

export interface LadderRow {
  run_id: string;
  level: number;
  title: string;
  agent: string;
  error?: string | null;
  guilty: number;
  found: number;
  schemes_total: number;
  schemes_described: number;
  false_positive_providers: number;
  tool_calls?: number;
  seconds?: number;
  input_tokens?: number;
  output_tokens?: number;
}

export interface AnswerKey {
  level: number;
  title: string;
  description: string;
  guilty: Record<string, {
    name: string;
    details: Record<string, string>;
    schemes: Record<string, { claims: number; paid: number }>;
  }>;
}
