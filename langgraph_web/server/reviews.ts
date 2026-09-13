import { readFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import { Annotation, StateGraph, MemorySaver, START, END, interrupt, Command } from '@langchain/langgraph'
import { z } from 'zod'
import type { Claim, Decision, Review } from '../shared/types.ts'

const claimSchema = z.object({ id:z.string(), member:z.string(), plan:z.string(), status:z.enum(['PENDING_REVIEW','PAID','DENIED','PARTIAL']), reason:z.string(), amount:z.number().nonnegative() })
export const decisionSchema = z.object({ action:z.enum(['approve','reject']), reason:z.string().trim().min(1).max(1000), text:z.string().trim().min(1).max(8000) }).strict()
export const claims: Claim[] = z.array(claimSchema).parse(JSON.parse(readFileSync(new URL('./data/claims.json',import.meta.url),'utf8')))
const State = Annotation.Root({ claimId:Annotation<string>(), draft:Annotation<string>(), answer:Annotation<string>(), decision:Annotation<Decision | undefined>() })
export class HttpError extends Error { constructor(public status:number,message:string){super(message)} }

export function createReviews() {
 const saver = new MemorySaver()
 const graph = new StateGraph(State)
 .addNode('explain', (s) => {
   const c=claims.find(c=>c.id===s.claimId)
   if(!c) throw new HttpError(404,'Claim not found')
   return {draft:`SIMULATION ONLY\n\nClaim ${c.id} has recorded status ${c.status}.\n\n${c.reason}\n\nNext step: have the demo reviewer verify this explanation. Approval releases this text only; it does not change the insurance claim.`,answer:''}
 })
 .addNode('human_review', (s) => {
   const d=decisionSchema.parse(interrupt({draft:s.draft}))
   return {decision:d,answer:d.action==='approve'?d.text:'Explanation rejected. No response released.'}
 })
 .addEdge(START,'explain').addEdge('explain','human_review').addEdge('human_review',END)
 .compile({checkpointer:saver})
 const records=new Map<string,Review>()
 const starts=new Map<string,{claimId:string;promise:Promise<Review>}>()
 const busy=new Set<string>()
 const submitted=new Map<string,{payload:string;result:Review}>()
 const cfg=(id:string)=>({configurable:{thread_id:id}})
 function get(id:string){const r=records.get(id);if(!r)throw new HttpError(404,'Review not found; the server may have restarted');return r}
 return {
  list:()=>[...records.values()].reverse(), get,
  start(claimId:string,requestId:string):Promise<Review>{
   const prior=starts.get(requestId)
   if(prior){if(prior.claimId!==claimId)throw new HttpError(409,'Request ID reused with different claim');return prior.promise}
   if(!claims.some(c=>c.id===claimId))throw new HttpError(404,'Claim not found')
   if(starts.size>=200)throw new HttpError(429,'Demo session limit reached. Restart the backend to clear memory.')
   const promise=(async()=>{
    const id=randomUUID(); const s=await graph.invoke({claimId},cfg(id))
    const r:Review={id,claimId,createdAt:new Date().toISOString(),status:'waiting',draft:s.draft,answer:s.answer}
    records.set(id,r);return r
   })()
   starts.set(requestId,{claimId,promise});return promise
  },
  async review(id:string,raw:unknown,requestId:string){
   const d=decisionSchema.parse(raw); const key=id+':'+requestId; const payload=JSON.stringify(d)
   const old=submitted.get(key)
   if(old){if(old.payload!==payload)throw new HttpError(409,'Request ID reused with different decision');return old.result}
   const current=get(id)
   if(busy.has(id)||current.status!=='waiting')throw new HttpError(409,'Case is being processed or already reviewed')
   busy.add(id)
   try {
    const s=await graph.invoke(new Command({resume:d}),cfg(id))
    const r:Review={...current,status:d.action==='approve'?'approved':'rejected',decision:d,answer:s.answer}
    records.set(id,r);submitted.set(key,{payload,result:r});return r
   } finally {busy.delete(id)}
  },
  async history(id:string){get(id);const rows=[];for await(const s of graph.getStateHistory(cfg(id)))rows.push({createdAt:s.createdAt,next:s.next,state:s.values});return rows.reverse()}
 }
}
