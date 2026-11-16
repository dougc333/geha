import React from "react";
import ReactDOM from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useMemo, useState } from "react";
import "./style.css";

type Pair = { id: string; name: string; pdf?: File; markdown?: File; pdfUrl?: string; markdownKey?: string; status?: string };

function baseName(file: File): string {
  return file.name.replace(/\.(pdf|md)$/i, "").toLowerCase();
}

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [awsPairs, setAwsPairs] = useState<Pair[]>([]);
  const [selected, setSelected] = useState("");
  const [text, setText] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  const pairs = useMemo(() => {
    const byName = new Map<string, Pair>();
    for (const file of files) {
      if (!/\.(pdf|md)$/i.test(file.name)) continue;
      const name = baseName(file);
      const pair = byName.get(name) ?? { id: `local:${name}`, name };
      if (/\.pdf$/i.test(file.name)) pair.pdf = file;
      else pair.markdown = file;
      byName.set(name, pair);
    }
    return [...byName.values()].concat(awsPairs).sort((a, b) => a.name.localeCompare(b.name));
  }, [files, awsPairs]);
  const active = pairs.find((pair) => pair.id === selected) ?? pairs[0];

  useEffect(() => {
    if (!active?.pdf) {
      setPdfUrl(active?.pdfUrl ?? "");
      return;
    }
    const url = URL.createObjectURL(active.pdf);
    setPdfUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [active?.pdf, active?.pdfUrl]);

  useEffect(() => {
    let current = true;
    setText("");
    setError("");
    const source = active?.markdown
      ? active.markdown.text()
      : active?.markdownKey
        ? fetch(`/api/markdown?key=${encodeURIComponent(active.markdownKey)}`).then(async (response) => {
            if (!response.ok) throw new Error(`Markdown request failed: ${response.status}`);
            return response.text();
          })
        : null;
    if (source) {
      source.then((value) => {
        if (current) setText(value);
      }).catch((reason) => {
        if (current) setError(String(reason));
      });
    }
    return () => { current = false; };
  }, [active?.markdown, active?.markdownKey]);

  async function loadAws(selectFirst = true) {
    if (selectFirst) setError("");
    try {
      const response = await fetch("/api/documents");
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `AWS request failed: ${response.status}`);
      setAwsPairs((previous) => {
        if (selectFirst) return result as Pair[];
        const urls = new Map(previous.map((pair) => [pair.id, pair.pdfUrl]));
        return (result as Pair[]).map((pair) => ({
          ...pair,
          pdfUrl: urls.get(pair.id) ?? pair.pdfUrl,
        }));
      });
      if (selectFirst && result.length) setSelected(result[0].id);
    } catch (reason) {
      setError(String(reason));
    }
  }

  useEffect(() => {
    if (!awsPairs.some((pair) => pair.status === "processing")) return;
    const timer = window.setInterval(() => { void loadAws(false); }, 5000);
    return () => window.clearInterval(timer);
  }, [awsPairs]);

  async function uploadPdf(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const response = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`, {
        method: "POST", headers: { "Content-Type": "application/pdf" }, body: file,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Upload failed: ${response.status}`);
      await loadAws(false);
      setSelected(`aws:${result.name.slice(0, -4)}`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setUploading(false);
    }
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((old) => [...old, ...Array.from(list)]);
  }

  return (
    <div className="app">
      <header>
        <div><span className="eyebrow">DOCUMENT REVIEW</span><h1>PDF and extraction</h1></div>
        <div className="actions">
          <button onClick={() => { void loadAws(); }}>Load AWS outputs</button>
          <label className="upload">{uploading ? "Uploading…" : "Upload PDF and process"}<input type="file" accept=".pdf" disabled={uploading} onChange={(event) => { void uploadPdf(event.target.files?.[0]); event.target.value = ""; }} /></label>
          <label className="upload">Add PDFs and Markdown<input type="file" accept=".pdf,.md" multiple onChange={(event) => addFiles(event.target.files)} /></label>
          <label className="upload secondary">Open run folder<input type="file" multiple {...{ webkitdirectory: "" }} onChange={(event) => addFiles(event.target.files)} /></label>
          <button onClick={() => { setFiles([]); setAwsPairs([]); setSelected(""); setError(""); }}>Clear</button>
        </div>
      </header>
      <div className="toolbar">
        <label>Document <select value={active?.id ?? ""} onChange={(event) => setSelected(event.target.value)}>
          {pairs.map((pair) => <option key={pair.id} value={pair.id}>{pair.name}{pair.status === "processing" ? " · processing" : pair.markdownKey ? " · AWS" : " · local"}{!pair.pdf && !pair.pdfUrl ? " · PDF missing" : ""}{!pair.markdown && !pair.markdownKey ? " · Markdown missing" : ""}</option>)}
        </select></label>
        <span>{pairs.length} document{pairs.length === 1 ? "" : "s"}</span>
      </div>
      <main>
        <section className="pane"><div className="panehead"><h2>Source PDF</h2><span>{active?.pdf?.name ?? (active?.pdfUrl ? `${active.name}.pdf` : "No PDF selected")}</span></div>
          {pdfUrl ? <iframe title="Multipage source PDF" src={pdfUrl} /> : <div className="empty">Select a PDF to view its pages.</div>}
        </section>
        <section className="pane"><div className="panehead"><h2>Extracted Markdown</h2><span>{active?.markdown?.name ?? active?.markdownKey ?? "No Markdown selected"}</span></div>
          <div className="markdown">{error ? <div className="error">{error}</div> : text ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown> : <div className="empty">{active?.status === "processing" ? "Processing on AWS; waiting for Markdown…" : "Select the matching .md file to inspect the extraction."}</div>}</div>
        </section>
      </main>
      <footer>Upload starts a temporary AWS task and incurs usage charges. AWS access uses your local profile through the Vite server.</footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
