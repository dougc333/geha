import React from "react";
import ReactDOM from "react-dom/client";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useMemo, useState } from "react";
import "./style.css";

type Pair = { id: string; name: string; pdf?: File; markdown?: File; pdfUrl?: string; markdownKey?: string; status?: string };
type TaskStatus = { status: string; detail: string; taskId?: string; heartbeatAgeSeconds?: number; messages: Array<{ time: string; message: string }> };
type BucketObject = { key: string; size: number; modified: string };
type BucketListing = { bucket: string; prefix: string; folders: string[]; objects: BucketObject[]; nextCursor?: string };
type ModelInventory = { cache_root: string; cached_models: Array<{ name: string; cache_path: string }>; downloaded_models: Array<{ name: string; cache_path: string }>; pipeline: { table_structure: boolean; chart_extraction: boolean; picture_images: boolean }; figures: number };
type ModelInfo = { localCacheRoot: string; localModels: string[]; runInventory: ModelInventory | null };

function baseName(file: File): string {
  return file.name.replace(/\.(pdf|md)$/i, "").toLowerCase();
}

function markdownUrl(url: string): string {
  return /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url) ? url : defaultUrlTransform(url);
}

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [awsPairs, setAwsPairs] = useState<Pair[]>([]);
  const [selected, setSelected] = useState("");
  const [text, setText] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [bucketOpen, setBucketOpen] = useState(false);
  const [bucketListing, setBucketListing] = useState<BucketListing | null>(null);
  const [bucketObjects, setBucketObjects] = useState<BucketObject[]>([]);
  const [bucketError, setBucketError] = useState("");
  const [bucketLoading, setBucketLoading] = useState(false);
  const [selectedObject, setSelectedObject] = useState("");
  const [objectText, setObjectText] = useState("");
  const [modelsOpen, setModelsOpen] = useState(false);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [modelError, setModelError] = useState("");

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
  const taskMessages = taskStatus?.messages ?? [];
  const taskStep = taskStatus?.status === "complete" ? 4
    : taskMessages.some((line) => line.message.startsWith("uploading Markdown")) ? 3
    : taskStatus?.status === "converting" || taskMessages.some((line) => line.message.includes("Loading weights")) ? 2
    : taskStatus?.status === "starting" ? 1 : 0;
  const taskStage = ["Queued", "Starting container", "Converting PDF", "Uploading Markdown", "Complete"][taskStep];

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

  useEffect(() => {
    if (!active?.id.startsWith("aws:")) { setTaskStatus(null); return; }
    let current = true;
    const name = active.id.slice(4);
    async function refreshStatus() {
      try {
        const response = await fetch(`/api/status?name=${encodeURIComponent(name)}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error ?? `Status request failed: ${response.status}`);
        if (current) setTaskStatus(result as TaskStatus);
      } catch (reason) {
        if (current) setTaskStatus({ status: "unavailable", detail: String(reason), messages: [] });
      }
    }
    setTaskStatus(null);
    void refreshStatus();
    const timer = window.setInterval(() => { void refreshStatus(); }, 5000);
    return () => { current = false; window.clearInterval(timer); };
  }, [active?.id]);

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

  async function loadBucket(prefix = "", cursor?: string) {
    setBucketLoading(true);
    setBucketError("");
    try {
      const params = new URLSearchParams({ prefix });
      if (cursor) params.set("cursor", cursor);
      const response = await fetch(`/api/bucket?${params}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Bucket request failed: ${response.status}`);
      setBucketListing(result as BucketListing);
      setBucketObjects((old) => cursor ? [...old, ...(result as BucketListing).objects] : (result as BucketListing).objects);
      if (!cursor) setSelectedObject("");
    } catch (reason) {
      setBucketError(String(reason));
    } finally {
      setBucketLoading(false);
    }
  }

  useEffect(() => {
    if (!selectedObject || !/\.(md|json|csv|txt)$/i.test(selectedObject)) { setObjectText(""); return; }
    let current = true;
    fetch(`/api/object?key=${encodeURIComponent(selectedObject)}`).then(async (response) => {
      if (!response.ok) throw new Error(`Object request failed: ${response.status}`);
      return response.text();
    }).then((value) => { if (current) setObjectText(value); })
      .catch((reason) => { if (current) setObjectText(String(reason)); });
    return () => { current = false; };
  }, [selectedObject]);

  const objectUrl = selectedObject ? `/api/object?key=${encodeURIComponent(selectedObject)}` : "";
  const prefixParts = bucketListing?.prefix.split("/").filter(Boolean) ?? [];

  useEffect(() => {
    if (!modelsOpen) return;
    let current = true;
    const name = active?.id.startsWith("aws:") ? active.id.slice(4) : "";
    fetch(`/api/models?name=${encodeURIComponent(name)}`).then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Models request failed: ${response.status}`);
      return result as ModelInfo;
    }).then((result) => { if (current) { setModelInfo(result); setModelError(""); } })
      .catch((reason) => { if (current) setModelError(String(reason)); });
    return () => { current = false; };
  }, [modelsOpen, active?.id, taskStatus?.status]);

  return (
    <div className="app">
      <header>
        <div><span className="eyebrow">DOCUMENT REVIEW</span><h1>PDF and extraction</h1></div>
        <div className="actions">
          <button onClick={() => { void loadAws(); }}>Load AWS outputs</button>
          <button aria-expanded={bucketOpen} aria-controls="bucket-browser" onClick={() => { setBucketOpen((old) => !old); setModelsOpen(false); if (!bucketOpen && !bucketListing) void loadBucket(); }}>{bucketOpen ? "Close S3 files" : "S3 bucket files"}</button>
          <button aria-expanded={modelsOpen} aria-controls="model-panel" onClick={() => { setModelsOpen((old) => !old); setBucketOpen(false); }}>{modelsOpen ? "Close models" : "Docling models"}</button>
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
      {active?.id.startsWith("aws:") && <section className="task-status" aria-live="polite">
        <div className="task-heading"><strong>Docling container: {taskStatus?.status ?? "checking"}</strong>
          <span>{taskStatus?.taskId ? `ECS task ${taskStatus.taskId}` : "Waiting for task ID"}</span></div>
        <div>{taskStatus?.detail ?? "Checking AWS task status…"}</div>
        {taskStatus?.heartbeatAgeSeconds !== undefined && <div>Last worker heartbeat: {taskStatus.heartbeatAgeSeconds}s ago</div>}
        <div className="task-progress-label">{taskStatus?.status === "failed" ? "Failed during " : "Stage "}{taskStep} of 4: {taskStage}</div>
        <progress className="task-progress" max={4} value={taskStep} aria-label="Docling task stage progress" />
        <pre className="task-log">{taskStatus?.messages.length
          ? taskStatus.messages.map((line) => `${line.time} ${line.message}`).join("\n")
          : "No container logs yet."}</pre>
      </section>}
      <main>
        <section className="pane"><div className="panehead"><h2>Source PDF</h2><span>{active?.pdf?.name ?? (active?.pdfUrl ? `${active.name}.pdf` : "No PDF selected")}</span></div>
          {pdfUrl ? <iframe title="Multipage source PDF" src={pdfUrl} /> : <div className="empty">Select a PDF to view its pages.</div>}
        </section>
        <section className="pane"><div className="panehead"><h2>Extracted Markdown</h2><span>{active?.markdown?.name ?? active?.markdownKey ?? "No Markdown selected"}</span></div>
          <div className="markdown">{error ? <div className="error">{error}</div> : text ? <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={markdownUrl}>{text}</ReactMarkdown> : <div className="empty">{taskStatus?.status === "failed" ? "Conversion failed; see the container log above." : active?.status === "processing" ? "Processing on AWS; waiting for Markdown…" : "Select the matching .md file to inspect the extraction."}</div>}</div>
        </section>
      </main>
      {bucketOpen && <section className="bucket-browser" id="bucket-browser" role="dialog" aria-label="S3 bucket files" aria-modal="true">
        <div className="bucket-heading"><div><h2>S3 bucket files</h2><span>{bucketListing?.bucket ?? "Loading bucket…"}</span></div>
          <div className="panel-actions"><button onClick={() => { void loadBucket(bucketListing?.prefix ?? ""); }} disabled={bucketLoading}>Refresh</button><button onClick={() => setBucketOpen(false)}>Close</button></div></div>
        <nav className="bucket-path" aria-label="S3 folder path">
          <button onClick={() => { void loadBucket(); }}>Bucket root</button>
          {prefixParts.map((part, index) => <React.Fragment key={`${part}-${index}`}><span>/</span><button onClick={() => { void loadBucket(`${prefixParts.slice(0, index + 1).join("/")}/`); }}>{part}</button></React.Fragment>)}
        </nav>
        {bucketError && <div className="error">{bucketError}</div>}
        <div className="bucket-layout"><div className="bucket-list">
          {bucketListing?.folders.map((prefix) => <button className="bucket-entry" key={prefix} onClick={() => { void loadBucket(prefix); }}>📁 {prefix.slice(bucketListing.prefix.length)}</button>)}
          {bucketObjects.map((object) => <button className={`bucket-entry ${selectedObject === object.key ? "selected" : ""}`} key={object.key} onClick={() => { setObjectText(""); setSelectedObject(object.key); }}>
            <span>📄 {object.key.slice((bucketListing?.prefix ?? "").length)}</span><small>{(object.size / 1024).toFixed(1)} KB · {object.modified ? new Date(object.modified).toLocaleString() : ""}</small>
          </button>)}
          {bucketListing?.nextCursor && <button onClick={() => { void loadBucket(bucketListing.prefix, bucketListing.nextCursor); }} disabled={bucketLoading}>Load more</button>}
          {!bucketLoading && bucketListing && !bucketListing.folders.length && !bucketObjects.length && <div className="empty">This folder is empty.</div>}
        </div><div className="bucket-preview">
          <div className="bucket-preview-head"><strong>{selectedObject || "Select a file"}</strong>{selectedObject && <a href={objectUrl} target="_blank" rel="noreferrer">Open file</a>}</div>
          {/\.pdf$/i.test(selectedObject) ? <iframe title="S3 PDF preview" src={objectUrl} />
            : /\.(png|jpe?g)$/i.test(selectedObject) ? <img src={objectUrl} alt={selectedObject} />
            : /\.(md|json|csv|txt)$/i.test(selectedObject) ? <pre>{objectText || "Loading…"}</pre>
            : <div className="empty">Select a PDF, image, Markdown, CSV, JSON, or text file to preview it.</div>}
        </div></div>
      </section>}
      {modelsOpen && <section className="model-panel" id="model-panel" role="dialog" aria-label="Docling models" aria-modal="true">
        <div className="panel-actions model-heading"><h2>Docling model downloads</h2><button onClick={() => setModelsOpen(false)}>Close</button></div>
        {modelError && <div className="error">{modelError}</div>}
        <div className="model-columns"><div><h3>Local Mac Hugging Face cache (shared)</h3><p>{modelInfo?.localCacheRoot ?? "Checking…"}</p>
          {modelInfo?.localModels.length ? <ul>{modelInfo.localModels.map((name) => <li key={name}>{name}</li>)}</ul> : <p>No Hugging Face model directories found.</p>}
        </div><div><h3>Selected Fargate run</h3>
          {modelInfo?.runInventory ? <><p>Cache: {modelInfo.runInventory.cache_root}</p>
            <p>Tables: {modelInfo.runInventory.pipeline.table_structure ? "on" : "off"} · Charts: {modelInfo.runInventory.pipeline.chart_extraction ? "on" : "off"} · Figure images: {modelInfo.runInventory.figures}</p>
            <h3>Downloaded during this run</h3>
            {modelInfo.runInventory.downloaded_models?.length ? <ul>{modelInfo.runInventory.downloaded_models.map((model) => <li key={model.name}>{model.name}</li>)}</ul> : <p>No new Hugging Face model directories recorded.</p>}
            <h3>Cached after the run</h3>
            {modelInfo.runInventory.cached_models.length ? <ul>{modelInfo.runInventory.cached_models.map((model) => <li key={model.name}>{model.name}</li>)}</ul> : <p>No Hugging Face cache directories recorded; weights bundled in the image are not listed.</p>}</>
            : <p>No model inventory for this run. Existing runs predate this feature; future runs will save one in S3.</p>}
        </div></div>
      </section>}
      <footer>Upload starts a temporary AWS task and incurs usage charges. AWS access uses your local profile through the Vite server.</footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
