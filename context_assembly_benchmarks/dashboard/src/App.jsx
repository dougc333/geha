import React, { useEffect, useMemo, useState } from "react";

const COLORS = { flat: "var(--s-flat)", table: "var(--s-table)", notes: "var(--s-notes)" };
const SLICES = [
  { id: "overall", label: "Overall", kind: null },
  { id: "preference", label: "Preference", kind: "Preference lookup" },
  { id: "relation", label: "Relation", kind: "Row-to-column relationship" },
  { id: "qualifier", label: "Qualifier", kind: "Qualifier" },
];
const CELLS = [
  { id: "correct", label: "Correct (in context, in answer)", short: "Correct", color: "var(--good)", icon: "✓" },
  { id: "generation_drop", label: "Generation drop (in context, left out)", short: "Generation drop", color: "var(--warning)", icon: "↓" },
  { id: "assembly_error", label: "Assembly error (never in context)", short: "Assembly error", color: "var(--critical)", icon: "✕" },
  { id: "unsupported", label: "Unsupported (in answer, not in context)", short: "Unsupported", color: "var(--serious)", icon: "!" },
];
const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const num = (v, d = 0) => (v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));

function useTooltip() {
  const [tip, setTip] = useState(null);
  const bind = (text) => ({
    onMouseMove: (e) => setTip({ text, x: e.clientX + 12, y: e.clientY + 12 }),
    onMouseLeave: () => setTip(null),
  });
  const node = tip ? <div className="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div> : null;
  return [bind, node];
}

function Status({ cell }) {
  const c = CELLS.find((x) => x.id === cell);
  return <span className="status"><i style={{ background: c.color }}>{c.icon}</i>{c.short}</span>;
}

function MetricBars({ title, strategies, values, format, note, bind, max }) {
  const top = max ?? Math.max(...strategies.map((s) => values[s.id] ?? 0), 1e-9);
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="bars">
        {strategies.map((s) => {
          const v = values[s.id];
          return (
            <div className="bar-row" key={s.id}>
              <span className="name">{s.label}</span>
              <div className="bar-track" {...bind(`${s.label}: ${format(v)}`)}>
                <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(1, (v ?? 0) / top)) * 100}%`, background: COLORS[s.id] }} />
              </div>
              <span className="val">{format(v)}</span>
            </div>
          );
        })}
      </div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}

function Legend({ strategies }) {
  return (
    <div className="legend">
      {strategies.map((s) => (
        <span key={s.id}><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}</span>
      ))}
    </div>
  );
}

function SliceFilter({ slice, setSlice, cases }) {
  return (
    <div className="seg" role="group" aria-label="Question slice">
      {SLICES.map((s) => (
        <button key={s.id} aria-pressed={slice === s.id} onClick={() => setSlice(s.id)}>
          {s.label}<span className="count">{s.kind ? cases.filter((c) => c.kind === s.kind).length : cases.length}</span>
        </button>
      ))}
    </div>
  );
}

function Mini({ value, color }) {
  return (
    <span className="mini">
      <span className="track"><span className="fill" style={{ display: "block", width: `${value * 100}%`, background: color }} /></span>
      {pct(value)}
    </span>
  );
}

/* ---------------------------------------------------------------- improvement ladder */

function improvementStages(data) {
  const table = data.answers?.summary?.table?.overall;
  const notes = data.answers?.summary?.notes?.overall;
  return [
    {
      id: "parent",
      label: "1. Parent-table expansion",
      status: "Measured",
      assemblyError: table?.cases_with_assembly_error,
      contextError: table == null ? null : 1 - table.context_complete_rate,
      answerError: table == null ? null : 1 - table.answer_complete_rate,
      code: "Expand each matching child row to its complete parent table.",
      detail: "Headers and sibling rows restore relationships, but nearby qualifiers and footnotes are still absent.",
    },
    {
      id: "notes",
      label: "2. Attach table notes",
      status: "Measured",
      assemblyError: notes?.cases_with_assembly_error,
      contextError: notes == null ? null : 1 - notes.context_complete_rate,
      answerError: notes == null ? null : 1 - notes.answer_complete_rate,
      code: "Attach the verified paragraph before the table and its linked notes after the table.",
      detail: "Every required fact now reaches the model. The remaining failures are generation drops, not retrieval or assembly failures.",
    },
    {
      id: "repair",
      label: "3. Verify + repair incomplete answers",
      status: "Target — rerun required",
      assemblyError: 0,
      contextError: 0,
      answerError: 0,
      code: "Check required facts against the draft answer; regenerate once with only the missing supported facts.",
      detail: "This is the intended next implementation. Zero answer error is a target until a fresh 59-case run measures it.",
    },
  ];
}

function ErrorMeter({ label, value, previous }) {
  const delta = previous == null || value == null ? null : previous - value;
  return (
    <div className="error-meter">
      <div className="error-meter-head">
        <span>{label}</span>
        <strong>{pct(value)}</strong>
      </div>
      <div className="error-track" aria-label={`${label}: ${pct(value)}`}>
        <span style={{ width: `${(value ?? 0) * 100}%` }} />
      </div>
      <div className="meta">
        {delta == null ? "Starting measured rate" : delta > 0 ? `Down ${pct(delta)} from the previous stage` : "Preserved at 0%"}
      </div>
    </div>
  );
}

function ImprovementView({ data }) {
  const [stageId, setStageId] = useState("parent");
  const stages = improvementStages(data);
  const index = stages.findIndex((s) => s.id === stageId);
  const stage = stages[index];
  const previous = index > 0 ? stages[index - 1] : null;
  return (
    <>
      <p className="sub">
        Turn improvements on cumulatively to see which failure class the code addresses. Measured stages use the saved
        59-question benchmark; the final stage is explicitly a target until it is rerun and verified.
      </p>
      <div className="stage-picker" role="radiogroup" aria-label="TableRAG implementation stage">
        {stages.map((s, i) => (
          <label key={s.id} className={s.id === stageId ? "selected" : ""}>
            <input type="radio" name="improvement-stage" value={s.id} checked={s.id === stageId} onChange={() => setStageId(s.id)} />
            <span className="stage-number">{i + 1}</span>
            <span><b>{s.label.replace(/^\d+\. /, "")}</b><small>{s.status}</small></span>
          </label>
        ))}
      </div>
      <div className="card improvement-card">
        <div>
          <span className={`evidence-badge ${stage.status.startsWith("Measured") ? "measured" : "target"}`}>{stage.status}</span>
          <h2>{stage.label}</h2>
          <p>{stage.detail}</p>
          <div className="code-change"><span>Code added</span>{stage.code}</div>
        </div>
        <div className="meter-grid">
          <ErrorMeter label="Assembly error" value={stage.assemblyError} previous={previous?.assemblyError} />
          <ErrorMeter label="Context incomplete" value={stage.contextError} previous={previous?.contextError} />
          <ErrorMeter label="Answer incomplete" value={stage.answerError} previous={previous?.answerError} />
        </div>
      </div>
      <div className="flow-strip" aria-label="TableRAG improvement flow">
        <span>Search row children</span><i>→</i><span>Expand parent table</span><i>→</i>
        <span className={index >= 1 ? "active" : "muted"}>Attach notes</span><i>→</i>
        <span className={index >= 2 ? "active" : "muted"}>Verify + repair</span>
      </div>
      <div className="notice">
        <b>Important:</b> 0% assembly error and 100% context completeness are measured for attached notes. A 0% answer-incomplete
        rate is not yet measured; it must come from the verifier/repair implementation followed by a new benchmark run.
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- context completeness */

function ContextView({ data, slice, strategies, bind, open }) {
  const ctx = data.context;
  const kind = SLICES.find((s) => s.id === slice).kind;
  const cases = ctx.cases.filter((c) => !kind || c.kind === kind);
  const sum = (key) => Object.fromEntries(strategies.map((s) => [s.id, ctx.summary[s.id]?.[slice]?.[key]]));
  const showQualifier = slice === "overall" || slice === "qualifier";
  return (
    <>
      <p className="sub">
        Is every fact a complete answer needs present in what each strategy sends to the model? No LLM involved:
        each required fact (table value or qualifier) is matched in the assembled context. Same BM25 + pgvector
        ranking for all three strategies.
      </p>
      <h2>Per strategy ({cases.length} questions)</h2>
      <div className="grid-3">
        {strategies.map((s) => {
          const v = ctx.summary[s.id]?.[slice] ?? {};
          return (
            <div className="card" key={s.id}>
              <div className="kpi-head"><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}</div>
              <div className="kpis">
                <div className="kpi"><div className="value">{pct(v.complete_evidence_rate)}</div><div className="label">questions with every fact in context</div></div>
                <div className="kpi"><div className="value">{showQualifier ? pct(v.qualifier_coverage) : "—"}</div><div className="label">qualifier facts in context</div></div>
                <div className="kpi"><div className="value">{num(v.average_estimated_tokens)}</div><div className="label">avg context tokens (est.)</div></div>
                <div className="kpi"><div className="value">{num(v.average_sibling_rows, 1)}</div><div className="label">avg sibling rows sent, not needed</div></div>
              </div>
            </div>
          );
        })}
      </div>
      <h2>Compare</h2>
      <div className="grid-metrics">
        <MetricBars title="Questions with every fact in context" strategies={strategies} values={sum("complete_evidence_rate")} format={pct} bind={bind} max={1}
          note="Missing facts here are assembly errors: the model can't use what it never receives." />
        <MetricBars title="Required facts in context (avg)" strategies={strategies} values={sum("average_evidence_coverage")} format={pct} bind={bind} max={1} />
        {showQualifier && (
          <MetricBars title="Qualifier facts in context" strategies={strategies} values={sum("qualifier_coverage")} format={pct} bind={bind} max={1}
            note="Footnotes, exceptions and authorization periods stored beside the table." />
        )}
        <MetricBars title="Avg context tokens (est., lower is cheaper)" strategies={strategies} values={sum("average_estimated_tokens")} format={(v) => num(v)} bind={bind} />
        <MetricBars title="Avg sibling rows sent but not needed" strategies={strategies} values={sum("average_sibling_rows")} format={(v) => num(v, 1)} bind={bind}
          note="Rows in the context that carry no required value: the cost of parent-table expansion." />
      </div>
      <Legend strategies={strategies} />
      <h2>Questions</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Question</th><th>Type</th>{strategies.map((s) => <th key={s.id}>{s.label}</th>)}<th className="num">Tokens (flat / table / +notes)</th></tr></thead>
          <tbody>
            {cases.map((c, i) => (
              <tr key={`${c.id}-${i}`} className="click" onClick={() => open({ type: "context", c })}>
                <td>{c.query}<div className="meta">{c.id}</div></td>
                <td><span className="tag">{c.kind.replace("Row-to-column relationship", "Relation").replace("Preference lookup", "Preference")}</span></td>
                {strategies.map((s) => <td key={s.id}><Mini value={c.strategies[s.id]?.coverage ?? 0} color={COLORS[s.id]} /></td>)}
                <td className="num">{strategies.map((s) => num(c.strategies[s.id]?.tokens)).join(" / ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- answer completeness */

function AnswerView({ data, slice, strategies, bind, open }) {
  const ans = data.answers;
  if (!ans) {
    return (
      <div className="notice">
        Answer completeness hasn't been run yet (or is still running). Run
        <code>evaluate_chunking_judge.py --resume</code>, then <code>npm run data</code>, and reload.
      </div>
    );
  }
  const kind = SLICES.find((s) => s.id === slice).kind;
  const cases = ans.cases.filter((c) => !kind || c.kind === kind);
  const get = (s, key) => ans.summary[s]?.[slice]?.[key];
  const vals = (key) => Object.fromEntries(strategies.map((s) => [s.id, get(s.id, key)]));
  return (
    <>
      <p className="sub">
        Does the answer state every required fact? Each fact is checked in the context and in the answer, which
        separates <b>assembly errors</b> (never sent to the model) from <b>generation drops</b> (sent, then left out).
        Answer, judge and fact check: {ans.configuration.answer_model} / {ans.configuration.judge_model}.
        {ans.summary.queries_completed < ans.summary.queries_requested && ` ${ans.summary.queries_completed} of ${ans.summary.queries_requested} questions completed.`}
      </p>
      <h2>Per strategy ({cases.length} questions)</h2>
      <div className="grid-3">
        {strategies.map((s) => (
          <div className="card" key={s.id}>
            <div className="kpi-head"><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}</div>
            <div className="kpis">
              <div className="kpi"><div className="value">{pct(get(s.id, "answer_complete_rate"))}</div><div className="label">answers with every fact</div></div>
              <div className="kpi"><div className="value">{pct(get(s.id, "judge_yes_rate"))}</div><div className="label">judge says it answers the question</div></div>
              <div className="kpi"><div className="value">{pct(get(s.id, "cases_with_assembly_error"))}</div><div className="label">questions with an assembly error</div></div>
              <div className="kpi"><div className="value">{pct(get(s.id, "cases_with_generation_drop"))}</div><div className="label">questions with a generation drop</div></div>
            </div>
          </div>
        ))}
      </div>
      <h2>Where required facts end up</h2>
      <div className="card">
        {strategies.map((s) => {
          const cells = get(s.id, "fact_cells") || {};
          const total = get(s.id, "facts") || 1;
          return (
            <div className="stack-row" key={s.id}>
              <span className="mini"><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}</span>
              <div className="stack">
                {CELLS.map((cell) => {
                  const n = cells[cell.id] || 0;
                  if (!n) return null;
                  return (
                    <span key={cell.id} style={{ width: `${(n / total) * 100}%`, background: cell.color }} {...bind(`${s.label} - ${cell.label}: ${n} of ${total} facts (${pct(n / total)})`)}>
                      {n / total > 0.06 ? `${cell.icon} ${n}` : ""}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
        <div className="legend">{CELLS.map((c) => <span key={c.id}><Status cell={c.id} /> {c.label.replace(/^[^(]*/, "")}</span>)}</div>
      </div>
      <div className="grid-metrics" style={{ marginTop: 12 }}>
        <MetricBars title="Answers with every fact" strategies={strategies} values={vals("answer_complete_rate")} format={pct} bind={bind} max={1} />
        <MetricBars title="Context with every fact (same run)" strategies={strategies} values={vals("context_complete_rate")} format={pct} bind={bind} max={1}
          note="The gap between these two charts is generation drop." />
        <MetricBars title="Avg answer + judge + fact-check tokens" strategies={strategies} values={vals("average_llm_tokens")} format={(v) => num(v)} bind={bind} />
      </div>
      <h2>Questions</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Question</th><th>Type</th>{strategies.map((s) => <th key={s.id}>{s.label}</th>)}</tr></thead>
          <tbody>
            {cases.map((c, i) => (
              <tr key={`${c.id}-${i}`} className="click" onClick={() => !c.error && open({ type: "answer", c })}>
                <td>{c.query}<div className="meta">{c.id}</div></td>
                <td><span className="tag">{c.kind.replace("Row-to-column relationship", "Relation").replace("Preference lookup", "Preference")}</span></td>
                {c.error ? <td colSpan={3} className="meta">error: {c.error}</td> : strategies.map((s) => {
                  const facts = c.strategies[s.id].facts;
                  const lost = facts.filter((f) => f.cell !== "correct");
                  return (
                    <td key={s.id}>
                      {lost.length === 0 ? <Status cell="correct" /> : (
                        <span style={{ display: "grid", gap: 2 }}>
                          {CELLS.filter((x) => x.id !== "correct").map((x) => {
                            const n = lost.filter((f) => f.cell === x.id).length;
                            return n ? <span key={x.id}><Status cell={x.id} /> ×{n}</span> : null;
                          })}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- case drawer */

function Drawer({ item, strategies, close }) {
  const { type, c } = item;
  return (
    <div className="drawer-bg" onClick={close}>
      <div className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={c.id}>
        <button className="close" onClick={close}>Close</button>
        <h2 style={{ marginTop: 0 }}>{c.query}</h2>
        <div className="meta">{c.id} · {c.kind}</div>
        {strategies.map((s) => {
          const st = c.strategies[s.id];
          if (!st) return null;
          return (
            <div key={s.id} style={{ marginTop: 18 }}>
              <div className="kpi-head"><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}
                <span className="meta" style={{ marginTop: 0, fontWeight: 400 }}>
                  {type === "context" ? `~${num(st.tokens)} tokens · ${st.rows_sent} rows sent, ${st.sibling_rows} not needed` : `~${num(st.context_tokens)} context tokens · judge: ${st.judge.answers_query}`}
                </span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Required fact</th><th>Type</th><th>In context</th>{type === "answer" && <><th>In answer</th><th>Outcome</th></>}</tr></thead>
                  <tbody>
                    {st.facts.map((f, i) => (
                      <tr key={i}>
                        <td>{f.text}{type === "answer" && f.type === "qualifier" && <div className="meta">{f.reason}</div>}</td>
                        <td><span className="tag">{f.type}</span></td>
                        <td>{f.in_context ? "yes" : "no"}</td>
                        {type === "answer" && <><td>{f.in_answer ? "yes" : "no"}</td><td><Status cell={f.cell} /></td></>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {type === "answer" && <><h3 style={{ marginTop: 10 }}>Answer</h3><div className="answer">{st.answer}</div>
                <div className="meta">Judge: {st.judge.reason}</div></>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- method */

/* ---------------------------------------------------------------- summary */

function SummaryView({ data, slice, strategies, setTab }) {
  const ctx = data.context.summary;
  const ans = data.answers?.summary;
  const label = SLICES.find((s) => s.id === slice).label;
  // Columns: key, header, getter, better ("high" | "low"), source
  const cols = [
    { id: "retrieved", head: "Right table retrieved", get: (s) => ctx[s]?.[slice]?.expected_table_present_rate, fmt: pct, better: "high", note: "retrieval" },
    { id: "context", head: "Every fact in context ①", get: (s) => ans ? ans[s]?.[slice]?.context_complete_rate : ctx[s]?.[slice]?.complete_evidence_rate, fmt: pct, better: "high" },
    { id: "answer", head: "Answer has every fact ②", get: (s) => ans?.[s]?.[slice]?.answer_complete_rate, fmt: pct, better: "high" },
    { id: "assembly", head: "Questions with an assembly error", get: (s) => ans?.[s]?.[slice]?.cases_with_assembly_error, fmt: pct, better: "low" },
    { id: "drop", head: "Questions with a generation drop", get: (s) => ans?.[s]?.[slice]?.cases_with_generation_drop, fmt: pct, better: "low" },
    { id: "tokens", head: "Avg context tokens", get: (s) => ans ? ans[s]?.[slice]?.average_context_tokens : ctx[s]?.[slice]?.average_estimated_tokens, fmt: (v) => num(v), better: null },
  ];
  const best = Object.fromEntries(cols.map((c) => {
    if (!c.better) return [c.id, null];
    const vals = strategies.map((s) => c.get(s.id)).filter((v) => v != null);
    if (!vals.length) return [c.id, null];
    return [c.id, c.better === "high" ? Math.max(...vals) : Math.min(...vals)];
  }));
  const n = ctx.flat?.[slice]?.cases;
  return (
    <>
      <h2>Results{slice !== "overall" && ` · ${label} questions`} ({n} questions)</h2>
      <div className="table-wrap">
        <table className="summary">
          <thead>
            <tr><th>Strategy</th>{cols.map((c) => <th key={c.id} className="num">{c.head}</th>)}</tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.id}>
                <td><span className="mini"><i className="swatch" style={{ background: COLORS[s.id] }} />{s.label}</span></td>
                {cols.map((c) => {
                  const v = c.get(s.id);
                  const isBest = best[c.id] != null && v === best[c.id];
                  return <td key={c.id} className="num" style={isBest ? { fontWeight: 700 } : undefined}>{c.fmt(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="note">
        Bold = best in column (higher is better for coverage, lower for errors). "Right table retrieved" is the retrieval
        check: the gap between it and "Every fact in context" is facts lost after retrieval (assembly), not ranking misses.
        {!ans && " Answer columns appear once evaluation ② has been run."}
      </div>
      <div className="grid-3" style={{ marginTop: 16 }}>
        <div className="card"><h3>Assembly error</h3>A required fact never reached the model, because retrieval missed it or the context left it out. Fixed by context assembly (table-aware RAG, attached notes).</div>
        <div className="card"><h3>Generation drop</h3>The fact was in the context, but the answer left it out. Better retrieval can't fix this; a completeness check or prompt change can.</div>
        <div className="card"><h3>Explore</h3>
          <button className="theme" onClick={() => setTab("context")}>① Context completeness →</button>{" "}
          <button className="theme" onClick={() => setTab("answers")} style={{ marginTop: 6 }}>② Answer completeness →</button>
        </div>
      </div>
    </>
  );
}

function MethodView() {
  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>To measure it properly</h2>
      <ol className="steps">
        <li><b>Add qualifier cases to the 41:</b> footnotes (<code>**</code>), exceptions ("does not apply in…"), and conditions on other pages. Label each case's required facts, including those qualifiers.</li>
        <li><b>Run ① for flat, table-aware, and table-aware plus attached footnotes:</b> append text linked to the table (footnotes, the preceding paragraph) to the parent table. That's a cheap structural fix to test.</li>
        <li><b>Run ② once,</b> paying for answers and judging, and join per fact into the four-cell table.</li>
        <li><b>Report per strategy:</b> the share of cases with assembly errors, the share with generation drops, tokens used, and sibling-row noise (how many rows sent that weren't needed).</li>
      </ol>
      <h2>The four cells</h2>
      <table>
        <thead><tr><th>In context?</th><th>In answer?</th><th>Outcome</th><th>Who fixes it</th></tr></thead>
        <tbody>
          <tr><td>yes</td><td>yes</td><td><Status cell="correct" /></td><td>—</td></tr>
          <tr><td>yes</td><td>no</td><td><Status cell="generation_drop" /></td><td>Prompting, the model, a completeness check</td></tr>
          <tr><td>no</td><td>no</td><td><Status cell="assembly_error" /></td><td>Retrieval and context assembly (e.g. table-aware RAG, attached notes)</td></tr>
          <tr><td>no</td><td>yes</td><td><Status cell="unsupported" /></td><td>Groundedness check</td></tr>
        </tbody>
      </table>
      <h2>What's in this run</h2>
      <ul>
        <li><b>59 questions:</b> 34 preference lookups and 7 row-to-column questions (the original 41), plus 18 qualifier questions generated by <code>make_qualifier_cases.py</code>: 14 on whether preferred-product requirements apply to reauthorizations (it differs by policy), 3 on the authorization period, 1 on Xgeva's <code>**</code> footnote.</li>
        <li><b>Attached notes</b> (<code>context_attachments.py</code>) are the paragraph before and the notes after each parent table, taken from the verified docling Markdown, because the pgvector store keeps only table cells.</li>
        <li><b>Table values</b> are matched by text in both context and answer. <b>Qualifier facts</b> are matched by text in the context and by an LLM fact check in the answer, since answers paraphrase them.</li>
      </ul>
      <h2>Caveats</h2>
      <ul>
        <li>The qualifier facts were taken from the same notes the third strategy attaches, so its 100% context score on that slice is partly by construction. The answer side shows whether the model actually uses them.</li>
        <li>"Conditions on other pages" aren't covered yet: every qualifier here sits next to its table.</li>
        <li>Token counts are characters ÷ 4. LLM verdicts are evaluation signals, not ground truth; spot-check the drawers.</li>
      </ul>
    </div>
  );
}

/* ---------------------------------------------------------------- app */

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("summary");
  const [slice, setSlice] = useState("overall");
  const [item, setItem] = useState(null);
  const [theme, setTheme] = useState(null);
  const [bind, tooltip] = useTooltip();

  useEffect(() => {
    fetch("./data/dashboard.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setItem(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const strategies = data?.strategies ?? [];
  const cases = useMemo(() => data?.context.cases ?? [], [data]);
  if (error) return <div className="app"><div className="notice">Couldn't load data/dashboard.json ({error}). Run <code>npm run data</code>.</div></div>;
  if (!data) return <div className="app">Loading…</div>;
  const cfg = data.context.configuration;
  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Context assembly: completeness dashboard</h1>
          <p className="sub">Flat row chunks vs table-aware RAG vs table-aware + attached notes, over GEHA coverage-policy tables.</p>
          <div className="meta">
            {cfg.retrieval} · {cfg.embedding_model} · top {cfg.top_chunks} chunks / {cfg.top_tables} tables · {cfg.parent_tables} tables, {cfg.child_vectors} row vectors · data {data.generated_at}
          </div>
        </div>
        <button className="theme" onClick={() => setTheme((t) => ((t ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark" ? "light" : "dark"))}>
          Toggle theme
        </button>
      </header>
      <div className="toolbar">
        <div className="tabs" role="tablist">
          {[["summary", "Summary"], ["improve", "Improvement ladder"], ["context", "① Context completeness"], ["answers", "② Answer completeness"], ["method", "Method"]].map(([id, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>
          ))}
        </div>
        {tab !== "method" && tab !== "improve" && <SliceFilter slice={slice} setSlice={setSlice} cases={cases} />}
      </div>
      {tab === "summary" && <SummaryView data={data} slice={slice} strategies={strategies} setTab={setTab} />}
      {tab === "improve" && <ImprovementView data={data} />}
      {tab === "context" && <ContextView data={data} slice={slice} strategies={strategies} bind={bind} open={setItem} />}
      {tab === "answers" && <AnswerView data={data} slice={slice} strategies={strategies} bind={bind} open={setItem} />}
      {tab === "method" && <MethodView />}
      {item && <Drawer item={item} strategies={strategies} close={() => setItem(null)} />}
      {tooltip}
    </div>
  );
}
