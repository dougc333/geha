import { Search, SlidersHorizontal, Upload } from "lucide-react";
import { type ChangeEvent, useRef } from "react";
import { type Filter, useIngestionActions, useIngestionState } from "../store/ingestion";
import type { OcrEngine } from "../api";

export function Toolbar() {
  const runtimeOnly = import.meta.env.VITE_DEPLOYMENT_MODE === "runtime";
  const inputRef = useRef<HTMLInputElement>(null);
  const { query, filter, ocrEngine } = useIngestionState();
  const { search, setFilter, setOcrEngine, addFiles } = useIngestionActions();
  const onFiles = (event: ChangeEvent<HTMLInputElement>) => {
    void addFiles(Array.from(event.target.files ?? []).filter((file) => file.type === "application/pdf" || file.name.endsWith(".pdf")));
    event.target.value = "";
  };
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <label className="relative min-w-0 flex-1 md:max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-fog" />
          <input value={query} onChange={(event) => search(event.target.value)} className="field pl-9" placeholder="Search 18 documents" />
        </label>
        <label className="relative">
          <SlidersHorizontal size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fog" />
          <select value={filter} onChange={(event) => setFilter(event.target.value as Filter)} className="field appearance-none pl-9 pr-8">
            <option value="all">All stages</option>
            <option value="attention">Needs review</option>
            <option value="queued">Queued</option>
            <option value="extracting">Extracting</option>
            <option value="reviewing">Reviewing</option>
            <option value="embedding">Embedding</option>
            <option value="complete">Complete</option>
          </select>
        </label>
        {!runtimeOnly && <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.035] px-3 py-2">
          <span className="font-mono text-[9px] uppercase tracking-[.13em] text-fog">OCR</span>
          <select
            value={ocrEngine}
            onChange={(event) => setOcrEngine(event.target.value as OcrEngine)}
            className="bg-transparent text-xs text-white outline-none"
            aria-label="OCR engine"
          >
            <option value="deepseek">DeepSeek (default)</option>
            <option value="llamaparse">LlamaParse</option>
          </select>
        </label>}
      </div>
      {!runtimeOnly && <><input ref={inputRef} className="hidden" type="file" accept="application/pdf,.pdf" multiple onChange={onFiles} /><button className="button-secondary" onClick={() => inputRef.current?.click()}><Upload size={16} /> Add PDFs</button></>}
      {runtimeOnly && <span className="rounded-full border border-mint/25 bg-mint/10 px-3 py-2 font-mono text-[9px] uppercase tracking-[.14em] text-mint">Read-only AWS index</span>}
    </div>
  );
}
