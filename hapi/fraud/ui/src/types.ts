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
  score?: number | null;
  score_of?: number | null;
}

export interface AnswerKey {
  providers: Record<string, { name: string; facility: string; schemes: string[] }>;
  schemes: Record<string, { provider: string; claims: number; paid?: number; overpaid?: number; detail: string }>;
}
