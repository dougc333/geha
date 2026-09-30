import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AnswerKey, Finding, LadderRow, SavedRun, ScoreResult, ToolInfo, TraceEvent } from "./types";

type CallEvent = Extract<TraceEvent, { type: "tool_call" }>;
type ResultEvent = Extract<TraceEvent, { type: "tool_result" }>;

interface Step {
  step: number;
  thinking: string[];
  notes: string[];
  calls: { call: CallEvent; result?: ResultEvent }[];
}

const SCHEME_LABEL: Record<string, string> = {
  upcoding: "Upcoding",
  impossible_day: "Impossible day",
  after_death: "Billing after death",
  duplicates: "Duplicate billing",
  unbundling: "Unbundling",
  excessive_frequency: "Excessive frequency",
  phantom_patients: "Phantom patients",
};

function money(n?: number) {
  return n == null ? "" : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Group the flat event stream into model steps: reasoning, notes, and the tool calls it made. */
function buildSteps(events: TraceEvent[]): Step[] {
  const steps = new Map<number, Step>();
  const get = (n: number) => {
    if (!steps.has(n)) steps.set(n, { step: n, thinking: [], notes: [], calls: [] });
    return steps.get(n)!;
  };
  const byCallId = new Map<string, { call: CallEvent; result?: ResultEvent }>();
  const pending: { call: CallEvent; result?: ResultEvent }[] = [];
  for (const e of events) {
    if (e.type === "thinking") get(e.step).thinking.push(e.text);
    else if (e.type === "text") get(e.step).notes.push(e.text);
    else if (e.type === "tool_call") {
      const entry = { call: e };
      get(e.step).calls.push(entry);
      byCallId.set(e.call_id, entry);
      pending.push(entry);
    } else if (e.type === "tool_result") {
      if (!e.call_id) continue; // inner call of a capped wrapper (older traces); the outer result is kept
      const entry = byCallId.get(e.call_id) ?? pending.find((p) => !p.result && p.call.name === e.name);
      if (entry) entry.result = e;
    }
  }
  return [...steps.values()].sort((a, b) => a.step - b.step);
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [runs, setRuns] = useState<SavedRun[]>([]);
  const [key, setKey] = useState<AnswerKey | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [tab, setTab] = useState<"investigate" | "choices" | "history" | "ladder">("investigate");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/default_question").then((r) => r.json()).then((d) => setQuestion(d.question));
    fetch("/api/answer_key").then((r) => r.json()).then(setKey).catch(() => setKey(null));
    refreshRuns();
  }, []);

  function refreshRuns() {
    fetch("/api/runs").then((r) => r.json()).then(setRuns).catch(() => setRuns([]));
  }

  // Stream a run's events (live or saved) over Server-Sent Events.
  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setStatus("running");
    const source = new EventSource(`/api/runs/${runId}/events`);
    source.onmessage = (m) => {
      const event = JSON.parse(m.data) as TraceEvent;
      setEvents((prev) => [...prev, event]);
      if (event.type === "error") setStatus("error");
    };
    source.addEventListener("end", () => {
      source.close();
      setStatus((s) => (s === "error" ? s : "done"));
      refreshRuns();
    });
    source.onerror = () => source.close();
    return () => source.close();
  }, [runId]);

  useEffect(() => {
    if (status === "running") bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length, status]);

  async function start() {
    const r = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const d = await r.json();
    setRunId(d.run_id);
  }

  const startEvent = events.find((e) => e.type === "run_start") as Extract<TraceEvent, { type: "run_start" }> | undefined;
  const tools: ToolInfo[] = startEvent?.tools ?? [];
  const steps = useMemo(() => buildSteps(events), [events]);
  const final = events.find((e) => e.type === "final") as Extract<TraceEvent, { type: "final" }> | undefined;
  const done = events.find((e) => e.type === "done") as Extract<TraceEvent, { type: "done" }> | undefined;
  const error = events.find((e) => e.type === "error") as Extract<TraceEvent, { type: "error" }> | undefined;
  const lastCall = [...events].reverse().find((e) => e.type === "tool_call") as CallEvent | undefined;
  const scoreEvent = events.find((e) => e.type === "score") as (ScoreResult & { type: "score" }) | undefined;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of events) if (e.type === "tool_call") c[e.name] = (c[e.name] ?? 0) + 1;
    return c;
  }, [events]);
  const elapsed = events.length ? events[events.length - 1].t : 0;

  return (
    <div className="app">
      <header>
        <div className="title">
          <h1>Claims fraud investigation</h1>
          <span className="sub">LangGraph agent · Claude · FHIR MCP + claims analytics · synthetic data</span>
        </div>
        <div className="controls">
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} />
          <div className="buttons">
            <button className="primary" onClick={start} disabled={status === "running" || question.length < 5}>
              {status === "running" ? "Investigating…" : "Run investigation"}
            </button>
            <select value={runId ?? ""} onChange={(e) => e.target.value && setRunId(e.target.value)}>
              <option value="">Replay a saved run…</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id}{r.level ? ` · L${r.level}` : ""} · {r.status} · {r.tool_calls ?? "?"} calls{r.found != null ? ` · ${r.found}/${r.guilty} found` : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="stats">
          <Stat label="status" value={status} />
          <Stat label="model steps" value={String(steps.length)} />
          <Stat label="tool calls" value={String(Object.values(counts).reduce((a, b) => a + b, 0))} />
          <Stat label="elapsed" value={`${(done?.seconds ?? elapsed).toFixed(1)}s`} />
          {done && <Stat label="tokens in / out" value={`${done.usage.input_tokens.toLocaleString()} / ${done.usage.output_tokens.toLocaleString()}`} />}
        </div>
      </header>

      <nav className="tabs">
        {([["investigate", "Investigation"], ["choices", "Tool choices"], ["history", `Run history (${runs.length})`], ["ladder", "Difficulty ladder"]] as const).map(([id, label]) => (
          <button key={id} className={tab === id ? "tab active" : "tab"} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      {tab === "choices" && <ChoicesView steps={steps} tools={tools} counts={counts} runId={runId} />}
      {tab === "ladder" && <LadderView onOpen={(id) => { setRunId(id); setTab("investigate"); }} />}
      {tab === "history" && (
        <HistoryView runs={runs} current={runId} onOpen={(id) => { setRunId(id); setTab("investigate"); }} onRefresh={refreshRuns} />
      )}

      <main hidden={tab !== "investigate"}>
        <aside className="tools">
          <h2>Tools the agent can choose</h2>
          {(["fhir-mcp", "analytics"] as const).map((source) => (
            <div key={source} className="tool-group">
              <h3>{source === "fhir-mcp" ? "Raw records · FHIR MCP" : "Aggregates · claims analytics"}</h3>
              {tools.filter((t) => t.source === source).map((t) => (
                <div key={t.name} className={`tool ${t.source} ${lastCall?.name === t.name && status === "running" ? "active" : ""} ${counts[t.name] ? "used" : ""}`}
                     title={t.description}>
                  <div className="tool-name">
                    <code>{t.name}</code>
                    <span className="count">{counts[t.name] ?? 0}</span>
                  </div>
                  <div className="tool-desc">{t.description}</div>
                </div>
              ))}
            </div>
          ))}
          {!tools.length && <p className="muted">Start or replay a run to see the tools.</p>}
        </aside>

        <section className="timeline">
          <h2>Trace</h2>
          {!events.length && <p className="muted">The agent's reasoning, tool choices and results appear here as it works.</p>}
          {steps.map((s) => (
            <div key={s.step} className="step">
              <div className="step-head">Step {s.step}<DecisionStrip tools={tools} calls={s.calls} /></div>
              {s.thinking.map((t, i) => (
                <div key={`th${i}`} className="thinking"><span className="icon">💭</span>{t}</div>
              ))}
              {s.notes.map((t, i) => (
                <div key={`n${i}`} className="note">{t}</div>
              ))}
              {s.calls.length > 1 && <div className="parallel">{s.calls.length} tool calls in parallel</div>}
              {s.calls.map(({ call, result }) => (
                <details key={call.call_id} className={`call ${call.source}`}>
                  <summary>
                    <span className={`chip ${call.source}`}>{call.source === "fhir-mcp" ? "FHIR" : "analytics"}</span>
                    <code className="call-name">{call.name}</code>
                    <code className="args">{JSON.stringify(call.args)}</code>
                    <span className="meta">
                      {result ? `${result.ms} ms · ${(result.size / 1024).toFixed(1)} KB${result.truncated ? " · cut for model" : ""}${result.is_error ? " · error" : ""}` : "running…"}
                    </span>
                  </summary>
                  {result && <pre className={result.is_error ? "err" : ""}>{prettyPreview(result.preview, result.size)}</pre>}
                </details>
              ))}
            </div>
          ))}
          {error && <div className="error-box"><strong>Error:</strong> {error.message}</div>}
          <div ref={bottom} />
        </section>

        <aside className="findings">
          <h2>Findings</h2>
          {!final && <p className="muted">{status === "running" ? "Investigating…" : "No report yet."}</p>}
          {final?.findings && <FindingsTable findings={final.findings} />}
          {scoreEvent && <Scorecard result={scoreEvent} />}
          {final && (
            <details className="report">
              <summary>Full report</summary>
              <div className="markdown"><Markdown remarkPlugins={[remarkGfm]}>{final.text.replace(/```json[\s\S]*?```/, "")}</Markdown></div>
            </details>
          )}
          {key && (
            <div className="key">
              <button className="link" onClick={() => setShowKey((v) => !v)}>
                {showKey ? "Hide" : "Show"} planted answer key
              </button>
              {showKey && (
                <ul>
                  <li><strong>Level {key.level} · {key.title}</strong>: {key.description}</li>
                  {Object.entries(key.guilty).map(([ref, g]) => Object.entries(g.details).map(([name, detail]) => (
                    <li key={ref + name}><strong>{SCHEME_LABEL[name] ?? name}</strong> · {g.name} ({ref}) · {detail}</li>
                  )))}
                  {!Object.keys(key.guilty).length && <li>No fraud planted at this level.</li>}
                </ul>
              )}
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function prettyPreview(text: string, size: number) {
  let out = text;
  try {
    out = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    /* truncated or not JSON: show as is */
  }
  return size > text.length ? `${out}\n… (${size.toLocaleString()} bytes total, first ${text.length} shown)` : out;
}

function FindingsTable({ findings }: { findings: Finding[] }) {
  return (
    <table className="ftable">
      <thead>
        <tr><th>Provider</th><th>Scheme (agent's words)</th><th>Conf.</th><th>Claims</th><th>At risk</th></tr>
      </thead>
      <tbody>
        {findings.map((f, i) => (
          <tr key={i} title={f.evidence}>
            <td>{f.name || f.provider}<div className="muted small">{f.provider}</div></td>
            <td>{SCHEME_LABEL[f.scheme] ?? f.scheme}</td>
            <td>{f.confidence ?? ""}</td>
            <td className="num">{f.claims ?? ""}</td>
            <td className="num">{money(f.amount_at_risk)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Scorecard({ result }: { result: ScoreResult }) {
  return (
    <div className="scorecard">
      <h3>{result.guilty ? `Guilty providers found: ${result.found}/${result.guilty}` : "No fraud was planted at this level"}
        {result.schemes_total ? ` · schemes described ${result.schemes_described}/${result.schemes_total}` : ""}
        {` · false accusations: ${result.false_positive_providers}`}</h3>
      {result.providers.map((p) => (
        <div key={p.provider} className={`score ${p.found ? "hit" : "miss"}`}>
          <span>{p.found ? "✓" : "✗"}</span>
          <div>
            <strong>{p.name}</strong> <span className="muted small">{p.provider}</span>
            <div className="muted small">{Object.entries(p.schemes).map(([name, ok]) => `${ok ? "✓" : "✗"} ${SCHEME_LABEL[name] ?? name}`).join(" · ")}</div>
          </div>
        </div>
      ))}
      {result.false_positives.map((f, i) => (
        <div key={i} className="score miss">
          <span>!</span>
          <div><strong>{f.name || f.provider}</strong> accused, not planted <span className="muted small">{f.confidence} · {f.scheme}</span></div>
        </div>
      ))}
    </div>
  );
}

/** Why the choices matter: questions that more than one tool can answer. */
const OVERLAPS: { question: string; tools: string[] }[] = [
  { question: "Which providers stand out?", tools: ["provider_billing_summary", "top_services", "fhir_search"] },
  { question: "Is a provider paid more than peers for the same service?", tools: ["service_cost_by_provider", "provider_billing_summary", "fhir_search"] },
  { question: "Are there duplicate claims?", tools: ["find_duplicate_claims", "fhir_search"] },
  { question: "Are claims billed after a patient died?", tools: ["claims_after_patient_death", "fhir_search", "fhir_read"] },
  { question: "Is a provider's workload possible?", tools: ["provider_daily_load", "fhir_search"] },
  { question: "What does the actual record say?", tools: ["fhir_read", "fhir_search"] },
];

function DecisionStrip({ tools, calls }: { tools: ToolInfo[]; calls: { call: CallEvent }[] }) {
  if (!tools.length) return null;
  const used = new Map<string, number>();
  for (const { call } of calls) used.set(call.name, (used.get(call.name) ?? 0) + 1);
  return (
    <span className="strip" title="All tools available at this step; filled = chosen">
      {tools.map((t) => (
        <span key={t.name} className={`dot ${t.source} ${used.has(t.name) ? "on" : ""}`} title={`${t.name}${used.has(t.name) ? ` ×${used.get(t.name)}` : " (not chosen)"}`} />
      ))}
      <span className="strip-label">{used.size} of {tools.length} tools chosen</span>
    </span>
  );
}

function ChoicesView({ steps, tools, counts, runId }: { steps: Step[]; tools: ToolInfo[]; counts: Record<string, number>; runId: string | null }) {
  if (!tools.length) {
    return <section className="page"><p className="muted">Start or replay a run (Investigation or Run history tab) to see its tool choices.</p></section>;
  }
  const ordered = [...tools.filter((t) => t.source === "fhir-mcp"), ...tools.filter((t) => t.source === "analytics")];
  return (
    <section className="page">
      <h2>Tool choices · {runId}</h2>
      <p className="muted">At every step the agent had all {tools.length} tools available and chose which to call (several in parallel is common).
        Filled cells are the tools it chose at that step, with the count; empty cells were available but not chosen.
        The reasoning column is Claude's own summary of why.</p>
      <div className="matrix-wrap">
        <table className="matrix">
          <thead>
            <tr>
              <th>Step</th>
              {ordered.map((t) => (
                <th key={t.name} className={t.source} title={t.description}><div className="vertical">{t.name}</div></th>
              ))}
              <th className="why">Reasoning before choosing</th>
            </tr>
          </thead>
          <tbody>
            {steps.filter((s) => s.calls.length).map((s) => {
              const used = new Map<string, number>();
              for (const { call } of s.calls) used.set(call.name, (used.get(call.name) ?? 0) + 1);
              return (
                <tr key={s.step}>
                  <td className="num">{s.step}</td>
                  {ordered.map((t) => (
                    <td key={t.name} className={`cell ${used.has(t.name) ? `on ${t.source}` : ""}`}>{used.get(t.name) ?? ""}</td>
                  ))}
                  <td className="why">{(s.thinking[s.thinking.length - 1] ?? s.notes[0] ?? "").slice(0, 260)}</td>
                </tr>
              );
            })}
            <tr className="totals">
              <td>Total</td>
              {ordered.map((t) => <td key={t.name} className="num">{counts[t.name] ?? 0}</td>)}
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="spaced">Overlapping options: questions more than one tool can answer</h2>
      <table className="overlaps">
        <thead><tr><th>Question</th><th>Tools that can answer it (calls in this run)</th></tr></thead>
        <tbody>
          {OVERLAPS.map((o) => (
            <tr key={o.question}>
              <td>{o.question}</td>
              <td>
                {o.tools.map((name) => {
                  const t = tools.find((x) => x.name === name);
                  return (
                    <span key={name} className={`opt ${t?.source ?? ""} ${counts[name] ? "picked" : ""}`}>
                      <code>{name}</code> {counts[name] ?? 0}
                    </span>
                  );
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Raw FHIR tools can answer every question but return whole records (large, and cut at 30,000 characters for the model);
        the analytics tools return one aggregate. The agent's pattern shows how it trades them off: aggregates to find suspects, raw reads to confirm.</p>
    </section>
  );
}

function HistoryView({ runs, current, onOpen, onRefresh }: { runs: SavedRun[]; current: string | null; onOpen: (id: string) => void; onRefresh: () => void }) {
  return (
    <section className="page">
      <h2>Run history <button className="link small" onClick={onRefresh}>refresh</button></h2>
      <p className="muted">Every run is saved to <code>hapi/fraud/traces/&lt;run id&gt;.json</code>, including failed ones. Click a run to replay its trace.</p>
      <table className="history">
        <thead>
          <tr><th>Run</th><th>Level</th><th>Status</th><th>Found</th><th>False acc.</th><th>Steps</th><th>Tool calls</th><th>Time</th><th>Tokens in / out</th><th>Question / error</th></tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.run_id} className={r.run_id === current ? "current" : ""} onClick={() => onOpen(r.run_id)}>
              <td><code>{r.run_id}</code></td>
              <td>{r.level ? `${r.level} ${r.level_title ?? ""}` : "–"}</td>
              <td><span className={`badge ${r.status}`}>{r.status}</span></td>
              <td className="num">{r.found != null ? (r.guilty ? `${r.found}/${r.guilty}` : "n/a") : "–"}</td>
              <td className="num">{r.false_positive_providers ?? "–"}</td>
              <td className="num">{r.model_steps ?? "–"}</td>
              <td className="num">{r.tool_calls ?? "–"}</td>
              <td className="num">{r.seconds != null ? `${r.seconds}s` : "–"}</td>
              <td className="num">{r.input_tokens != null ? `${r.input_tokens.toLocaleString()} / ${r.output_tokens?.toLocaleString()}` : "–"}</td>
              <td className={r.error ? "err-text" : "muted"}>{r.error ?? r.question}</td>
            </tr>
          ))}
          {!runs.length && <tr><td colSpan={10} className="muted">No saved runs yet.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}

function LadderView({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<LadderRow[]>([]);
  useEffect(() => {
    fetch("/api/ladder").then((r) => r.json()).then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <section className="page">
      <h2>Difficulty ladder</h2>
      <p className="muted">Each level plants fraud of increasing difficulty (level 5 plants none) and runs the agent on it.
        Scoring is by provider: guilty providers named, whether the scheme described matches, and innocent providers accused.
        Run with <code>python ladder.py</code>; click a row to replay its trace.</p>
      <table className="history">
        <thead>
          <tr><th>Level</th><th>Agent</th><th>Guilty found</th><th>Schemes described</th><th>False accusations</th>
            <th>Tool calls</th><th>Time</th><th>Tokens in / out</th><th>Run</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.run_id} onClick={() => onOpen(r.run_id)}>
              <td><strong>{r.level}</strong> {r.title}</td>
              <td>{r.agent}</td>
              <td className="num">{r.error ? <span className="err-text">error</span> : r.guilty ? `${r.found}/${r.guilty}` : "n/a"}</td>
              <td className="num">{r.schemes_total ? `${r.schemes_described}/${r.schemes_total}` : "n/a"}</td>
              <td className={`num ${r.false_positive_providers ? "err-text" : ""}`}>{r.false_positive_providers}</td>
              <td className="num">{r.tool_calls ?? "–"}</td>
              <td className="num">{r.seconds != null ? `${r.seconds}s` : "–"}</td>
              <td className="num">{r.input_tokens != null ? `${r.input_tokens.toLocaleString()} / ${r.output_tokens?.toLocaleString()}` : "–"}</td>
              <td><code>{r.run_id}</code></td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={9} className="muted">No ladder runs yet.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
