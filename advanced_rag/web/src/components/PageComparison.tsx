import { ChevronLeft, ChevronRight, Copy, FileText, ScanText } from "lucide-react";
import { useEffect, useState } from "react";
import { ingestionApi, type IngestionRun, type PageManifest } from "../api";
import { useSelectedDocument } from "../store/ingestion";

export function PageComparison() {
  const document = useSelectedDocument();
  const [manifest, setManifest] = useState<PageManifest | null>(null);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setRuns([]);
    setSelectedRunId(null);
    if (!document) return;
    let cancelled = false;
    void ingestionApi.runs(document.id)
      .then((value) => {
        if (cancelled) return;
        setRuns(value);
        setSelectedRunId(value.find((run) => run.is_current)?.run_id ?? value[0]?.run_id ?? null);
      })
      .catch(() => {
        if (!cancelled) setSelectedRunId(document.runId ?? null);
      });
    return () => { cancelled = true; };
  }, [document?.id, document?.runId]);

  useEffect(() => {
    setManifest(null);
    setPageIndex(0);
    setMarkdown("");
    setError(null);
    if (!document || !selectedRunId) return;
    let cancelled = false;
    const refresh = () => void ingestionApi.runPageManifest(document.id, selectedRunId)
      .then((value) => {
        if (!cancelled) {
          setManifest(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Page manifest unavailable");
      });
    refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [document?.id, selectedRunId]);

  const page = manifest?.pages[pageIndex];
  const selectedRun = runs.find((run) => run.run_id === selectedRunId);
  const selectedEngine = selectedRun?.ocr_engine === "llamaparse" || selectedRun?.ocr_engine === "deepseek"
    ? selectedRun.ocr_engine
    : page?.ocr_engine ?? document?.ocrEngine ?? "deepseek";
  const engineLabel = selectedEngine === "llamaparse" ? "LlamaParse" : "DeepSeek";
  const markdownPath = selectedEngine === "llamaparse"
    ? page?.llamaparse_markdown ?? null
    : page?.deepseek_markdown ?? null;

  useEffect(() => {
    if (!document || !markdownPath) {
      setMarkdown("");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const load = selectedRunId
      ? ingestionApi.runArtifactText(document.id, selectedRunId, `pages/${markdownPath}`)
      : ingestionApi.artifactText(document.id, `pages/${markdownPath}`);
    void load
      .then((value) => {
        if (!cancelled) setMarkdown(value);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Markdown unavailable");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [document?.id, markdownPath, selectedRunId]);

  if (!document?.runId && !document?.pageManifest) return null;
  if (!manifest && !error) {
    return <section className="panel grid min-h-48 place-items-center text-xs text-fog">Loading page comparison…</section>;
  }
  if (!manifest || !page) {
    return <section className="panel p-5 text-xs text-amber-200">{error ?? "No page artifacts were produced."}</section>;
  }

  const setPage = (next: number) => setPageIndex(Math.min(Math.max(next, 0), manifest.pages.length - 1));
  return (
    <section id="page-comparison" className="panel scroll-mt-5 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
        <div>
          <p className="eyebrow">Page extraction inspector</p>
          <h2 className="mt-1 text-sm font-semibold text-white">Original PDF + extracted Markdown</h2>
        </div>
        <div className="flex items-center gap-2">
          {runs.length > 0 && (
            <label className="flex h-8 items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-2 font-mono text-[10px] text-fog">
              RUN
              <select
                aria-label="Previous ingestion run"
                className="max-w-[250px] bg-transparent text-white outline-none"
                value={selectedRunId ?? ""}
                onChange={(event) => setSelectedRunId(event.target.value)}
              >
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.is_current ? "Latest · " : ""}{run.ocr_engine} · {run.completed_at || run.created_at ? new Date(run.completed_at ?? run.created_at!).toLocaleString() : run.run_id}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button className="icon-button size-8" onClick={() => setPage(pageIndex - 1)} disabled={pageIndex === 0} aria-label="Previous page"><ChevronLeft size={15} /></button>
          <label className="flex h-8 items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-2 font-mono text-[10px] text-fog">
            PAGE
            <select className="bg-transparent text-white outline-none" value={pageIndex} onChange={(event) => setPage(Number(event.target.value))}>
              {manifest.pages.map((item, index) => <option key={item.page} value={index}>{item.page} / {manifest.pages.length}</option>)}
            </select>
          </label>
          <button className="icon-button size-8" onClick={() => setPage(pageIndex + 1)} disabled={pageIndex === manifest.pages.length - 1} aria-label="Next page"><ChevronRight size={15} /></button>
        </div>
      </div>

      <div className="grid min-h-[680px] lg:grid-cols-2">
        <div className="min-w-0 border-b border-white/10 lg:border-b-0 lg:border-r">
          <div className="flex h-11 items-center justify-between border-b border-white/10 px-4">
            <span className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[.14em] text-fog"><FileText size={14} className="text-mint" /> Original page {page.page}</span>
            <a className="text-[10px] text-mint hover:text-citron" href={ingestionApi.runPageSource(document.id, selectedRunId!, page.page)} target="_blank" rel="noreferrer">Open page PDF</a>
          </div>
          <iframe
            key={`${document.id}-${selectedRunId}-pdf-page-${page.page}`}
            title={`Original PDF page ${page.page}`}
            src={ingestionApi.runPageSource(document.id, selectedRunId!, page.page)}
            className="h-[635px] w-full bg-white"
          />
        </div>

        <div className="min-w-0 bg-[#081310]">
          <div className="flex h-11 items-center justify-between border-b border-white/10 px-4">
            <span className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[.14em] text-fog"><ScanText size={14} className="text-citron" /> {engineLabel} Markdown · page {page.page}</span>
            <div className="flex items-center gap-1">
              <button className="icon-button ml-1 size-7" onClick={() => void navigator.clipboard.writeText(markdown)} aria-label="Copy Markdown"><Copy size={12} /></button>
            </div>
          </div>
          <div className="h-[635px] overflow-auto p-5">
            {loading ? <p className="text-xs text-fog">Loading {engineLabel} Markdown…</p> : !markdownPath ? <p className="text-xs text-fog">Page {page.page} has not completed {engineLabel} extraction yet.</p> : error ? <p className="text-xs text-amber-200">{error}</p> : (
              <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-6 text-white/85">{markdown}</pre>
            )}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-5 py-3 font-mono text-[9px] uppercase tracking-[.12em] text-fog">
        <span>{markdownPath ? `${engineLabel} extraction complete` : `${engineLabel} extraction pending`}</span>
        <span>{page.issues.length ? page.issues.join(" · ") : "No page extraction issues"}</span>
      </div>
    </section>
  );
}
