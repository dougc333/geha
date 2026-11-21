import {useEffect, useMemo, useState} from 'react';

type Document = {path:string;title:string;pages:number|null;bytes:number};
type Result = {path:string;status:string;pages?:number;figure_candidates?:number;needs_ocr_pages?:number[];ocr_pages?:number[];document_id?:string;error?:string};
type Batch = {batch_id:string;status:string;created_at:string;documents:Result[]};
type BatchSummary = {batch_id:string;status:string;created_at:string;total:number;done:number};

async function json<T>(url:string, init?:RequestInit):Promise<T>{
  const response=await fetch(url,init);
  if(!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export default function App(){
  const [documents,setDocuments]=useState<Document[]>([]);
  const [selected,setSelected]=useState<string[]>([]);
  const [filter,setFilter]=useState('');
  const [batch,setBatch]=useState<Batch|null>(null);
  const [history,setHistory]=useState<BatchSummary[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [expanded,setExpanded]=useState<string|null>(null);
  const [pageChoice,setPageChoice]=useState<Record<string,number>>({});

  useEffect(()=>{json<{documents:Document[]}>('/api/documents').then(x=>setDocuments(x.documents)).catch(e=>setError(String(e)));},[]);
  useEffect(()=>{let active=true; const refresh=()=>json<{batches:BatchSummary[]}>('/api/batches').then(x=>{if(active)setHistory(x.batches)}).catch(()=>{});refresh();const id=setInterval(refresh,3000);return()=>{active=false;clearInterval(id)}},[]);
  useEffect(()=>{if(!batch || batch.status!=='running')return;let active=true;const id=setInterval(()=>{json<Batch>(`/api/batches/${batch.batch_id}`).then(x=>{if(active)setBatch(x)}).catch(e=>setError(String(e)))},1500);return()=>{active=false;clearInterval(id)}},[batch?.batch_id,batch?.status]);

  const shown=useMemo(()=>documents.filter(d=>`${d.title} ${d.path}`.toLowerCase().includes(filter.toLowerCase())),[documents,filter]);
  const selectedSet=new Set(selected);
  const done=batch?.documents.filter(x=>!['queued','running'].includes(x.status)).length??0;
  async function start(){try{setBusy(true);setError('');const value=await json<Batch>('/api/batches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({documents:selected})});setBatch(value);setExpanded(null)}catch(e){setError(String(e))}finally{setBusy(false)}}
  async function open(id:string){try{setError('');setBatch(await json<Batch>(`/api/batches/${id}`));setExpanded(null)}catch(e){setError(String(e))}}
  function toggle(path:string){setSelected(old=>old.includes(path)?old.filter(x=>x!==path):[...old,path])}

  return <div className="shell">
    <header className="top"><div className="brand"><div className="mark">B</div><div><strong>GEHA Batch Ingestion</strong><small>Independent evidence-first PDF pipeline</small></div></div><span className="badge">LOCAL BATCH</span></header>
    <main>
      <section className="hero"><p className="eyebrow">SOURCE CORPUS</p><h1>Process GEHA documents in batches</h1><p>Select public PDFs, extract page text, retain source-faithful figure crops, and review chart candidates before semantic reconstruction.</p><div className="stats"><span><b>{documents.length}</b> PDFs</span><span><b>{selected.length}</b> selected</span><span><b>{history.length}</b> recent batches</span></div></section>
      {error&&<div className="error" role="alert">{error}</div>}
      <div className="columns"><section className="panel library"><div className="panelhead"><div><p className="eyebrow">DOCUMENTS</p><h2>Choose source PDFs</h2></div><button className="primary" onClick={start} disabled={!selected.length||busy}>{busy?'Starting…':`Run ${selected.length} selected`}</button></div><div className="controls"><input aria-label="Filter documents" placeholder="Filter by title or path" value={filter} onChange={e=>setFilter(e.target.value)}/><button onClick={()=>setSelected(old=>Array.from(new Set([...old,...shown.map(x=>x.path)])))}>Select filtered</button><button onClick={()=>setSelected([])}>Clear</button></div><div className="documentlist">{shown.map(d=><label className="doc" key={d.path}><input type="checkbox" checked={selectedSet.has(d.path)} onChange={()=>toggle(d.path)}/><span><strong>{d.title}</strong><small>{d.path}</small></span><em>{d.pages??'?'} pages</em></label>)}</div></section>
      <aside className="panel runs"><div className="panelhead"><div><p className="eyebrow">PROCESSING</p><h2>Batch results</h2></div>{batch&&<span className="status">{batch.status.replaceAll('_',' ')}</span>}</div>{batch?<><div className="progress"><div style={{width:`${batch.documents.length?done/batch.documents.length*100:0}%`}}/></div><p className="muted">{done} of {batch.documents.length} documents complete · {batch.batch_id}</p><div className="resultlist">{batch.documents.map(item=><div className="result" key={item.path}><button onClick={()=>setExpanded(expanded===item.path?null:item.path)}><span><b>{item.path.split('/').at(-1)}</b><small>{item.status.replaceAll('_',' ')} {item.pages!=null&&`· ${item.pages} pages`} {item.figure_candidates!=null&&`· ${item.figure_candidates} figure candidates`}</small></span><span>{expanded===item.path?'−':'+'}</span></button>{expanded===item.path&&<div className="resultdetails">{item.error&&<p className="error">{item.error}</p>}{item.document_id&&<><a target="_blank" href={`/api/raw/${encodeURI(item.path)}`}>Source PDF</a><a target="_blank" href={`/api/artifacts/${batch.batch_id}/${item.document_id}/manifest.json`}>Document manifest</a><a target="_blank" href={`/api/artifacts/${batch.batch_id}/${item.document_id}/figure-bounding-boxes.json`}>Figure boxes</a>{item.pages!=null&&<label className="pageselect">Page <select value={pageChoice[item.path]??1} onChange={e=>setPageChoice(old=>({...old,[item.path]:Number(e.target.value)}))}>{Array.from({length:item.pages},(_,i)=><option value={i+1} key={i}>{i+1}</option>)}</select></label>}<a target="_blank" href={`/api/artifacts/${batch.batch_id}/${item.document_id}/pages/page-${String(pageChoice[item.path]??1).padStart(3,'0')}/page.html`}>Page HTML</a><a target="_blank" href={`/api/artifacts/${batch.batch_id}/${item.document_id}/pages/page-${String(pageChoice[item.path]??1).padStart(3,'0')}/figure-specs.json`}>Figure evidence</a><a target="_blank" href={`/api/artifacts/${batch.batch_id}/${item.document_id}/figure-specs/page-${String(pageChoice[item.path]??1).padStart(3,'0')}.json`}>Provisional page spec</a></>}{item.ocr_pages?.length?<p>OCR text extracted on pages {item.ocr_pages.join(', ')}; review before relying on it.</p>:null}{item.needs_ocr_pages?.length?<p>OCR still needed: pages {item.needs_ocr_pages.join(', ')}</p>:null}</div>}</div>)}</div></>:<p className="empty">Choose documents and start a batch to see progress here.</p>}
      <h3>Recent batches</h3><div className="history">{history.map(item=><button key={item.batch_id} onClick={()=>open(item.batch_id)}><span>{item.batch_id}</span><em>{item.done}/{item.total}</em></button>)}</div></aside></div>
    </main>
  </div>
}
