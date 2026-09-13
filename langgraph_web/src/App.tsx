import { useEffect, useState } from 'react'
import type { Claim, Review, Decision } from '../shared/types'
import { ClaimList } from './components/ClaimList'
import { ReviewPanel } from './components/ReviewPanel'
import { MemoryNotice } from './components/MemoryNotice'
async function api<T>(path:string, body?:unknown):Promise<T>{
 const r=await fetch('/api'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined)
 const data=await r.json();if(!r.ok)throw new Error(data.error??'Request failed');return data
}
export default function App(){
 const [claims,setClaims]=useState<Claim[]>([]),[reviews,setReviews]=useState<Review[]>([])
 const [claimId,setClaimId]=useState(''),[active,setActive]=useState<Review|null>(null)
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[history,setHistory]=useState<unknown>(null)
 const [loading,setLoading]=useState(true)
 async function load(){try{const [c,r]=await Promise.all([api<Claim[]>('/claims'),api<Review[]>('/reviews')]);setClaims(c);setReviews(r);setClaimId(id=>id||c[0]?.id||'');setError('')}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
 useEffect(()=>{void load()},[])
 const claim=claims.find(c=>c.id===claimId)
 async function start(){setBusy(true);setError('');try{const r=await api<Review>('/reviews',{claimId,requestId:crypto.randomUUID()});setActive(r);setHistory(null);await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function decide(d:Decision){if(!active)return;setBusy(true);setError('');try{const r=await api<Review>(`/reviews/${active.id}/decision`,{decision:d,requestId:crypto.randomUUID()});setActive(r);setHistory(null);await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <div className="min-h-screen bg-slate-50 text-slate-900">
  <header className="border-b border-slate-200 bg-white px-6 py-5 flex items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="rounded-xl bg-teal-800 px-3 py-2 text-white font-bold">G</span><div><p className="font-bold tracking-tight text-lg">GEHA <span className="font-normal text-slate-500">/ Review workspace</span></p><p className="text-sm text-slate-500">LangGraph · synthetic claim explanations</p></div></div><span className="text-xs font-bold tracking-widest text-teal-800 border border-teal-200 rounded-full px-3 py-2">LOCAL DEMO</span></header>
  <main className="max-w-7xl mx-auto p-5 md:p-8"><MemoryNotice/>
   {error&&<div role="alert" className="my-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error} <button className="underline ml-3" onClick={()=>void load()}>Reconnect</button></div>}
   <div className="grid lg:grid-cols-[300px_1fr] gap-7 mt-7"><aside><h2 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">Synthetic claims · {claims.length}</h2>
    {loading?<p>Loading claims…</p>:<ClaimList claims={claims} selected={claimId} disabled={busy} onSelect={id=>{setClaimId(id);setActive(null);setHistory(null)}}/>}
    <div className="mt-7 flex items-center justify-between"><h2 className="text-xs font-bold uppercase tracking-widest text-slate-500">Session reviews</h2><button disabled={busy} className="text-sm text-teal-800" onClick={()=>void load()}>Refresh</button></div>
    {!reviews.length&&<p className="text-sm text-slate-500 mt-3">New reviews will appear here.</p>}
    <div className="mt-3 space-y-2">{reviews.map(r=><button disabled={busy} key={r.id} className={`w-full rounded-lg p-3 text-left text-sm border ${active?.id===r.id?'border-teal-600 bg-teal-50':'border-slate-200 bg-white'}`} onClick={()=>{setActive(r);setClaimId(r.claimId);setHistory(null)}}><span className="font-semibold">{r.claimId}</span><span className="block text-slate-500">{r.status==='waiting'?'Awaiting explanation review':r.status} · {r.id.slice(0,8)}</span></button>)}</div>
   </aside><section className="min-w-0">{claim&&<><div className="flex flex-wrap items-start justify-between gap-4 mb-6"><div><p className="text-sm text-slate-500 mb-1">{claim.member} / {claim.plan}</p><h1 className="text-3xl font-semibold tracking-tight">{claim.id}</h1></div><button disabled={busy} className="primary" onClick={()=>void start()}>{busy?'Working…':'＋ Start new review'}</button></div>
    <div className="grid sm:grid-cols-3 gap-3 mb-6"><div className="metric"><p>Insurance claim</p><strong>{claim.status.replaceAll('_',' ')}</strong></div><div className="metric"><p>Submitted amount</p><strong>{new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(claim.amount)}</strong></div><div className="metric"><p>Explanation review</p><strong>{active?active.status==='waiting'?'Awaiting reviewer':active.status:'Not started'}</strong></div></div>
    <ReviewPanel key={active?.id??claim.id} claim={claim} review={active} busy={busy} onDecision={decide}/>
    {active&&<div className="mt-5"><p className="text-xs text-slate-500 break-all">Automatic thread ID: {active.id}</p><button disabled={busy} className="text-sm text-teal-800 underline mt-3" onClick={async()=>{try{setHistory(await api(`/reviews/${active.id}/history`))}catch(e){setError((e as Error).message)}}}>Inspect checkpoint history</button>{history!==null&&<pre className="mt-3 rounded-xl bg-slate-900 text-slate-100 p-5 text-xs overflow-auto max-h-80">{JSON.stringify(history,null,2)}</pre>}</div>}
   </>}</section></div><footer className="mt-10 border-t border-slate-200 pt-5 text-xs text-slate-500">Not affiliated with GEHA. Fabricated records. No real claim decisions, payments, authentication, or LLM calls.</footer>
  </main></div>
}
