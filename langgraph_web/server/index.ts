import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { resolve, extname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { z, ZodError } from 'zod'
import { createReviews, claims, HttpError } from './reviews.ts'

const service=createReviews()
const dist=resolve(fileURLToPath(new URL('../dist/',import.meta.url)))
const requestSchema=z.object({requestId:z.uuid(),claimId:z.string().min(1)}).strict()
const reviewSchema=z.object({requestId:z.uuid(),decision:z.unknown()}).strict()
const mime:Record<string,string>={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}
const server=createServer(
    async(req,res)=>{
        const send=(status:number,value:unknown)=>{
            res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});
            res.end(JSON.stringify(value)
        )
    }
 
 try{ 
    const origin=req.headers.origin
    if(origin&&!['http://127.0.0.1:4317','http://localhost:4317','http://127.0.0.1:4318','http://localhost:4318'].includes(origin))throw new HttpError(403,'Origin not allowed')
    const path=new URL(req.url??'/', 'http://localhost').pathname
    if(path.startsWith('/api')){
        if(req.method==='GET'){
        if(path==='/api/claims')
            return send(200,claims)
        if(path==='/api/reviews')
            return send(200,service.list())
        if(path==='/api/health')
            return send(200,{ok:true,storage:'MemorySaver'})
        const m=path.match(/^\/api\/reviews\/([a-f0-9-]+)(\/history)?$/)
        if(m)
            return send(200,m[2]?await service.history(m[1]):service.get(m[1]))
   }

   if(req.method==='POST'){
    if(!req.headers['content-type']?.startsWith('application/json'))
        throw new HttpError(415,'JSON required')
    let body='';
    for await(const chunk of req){
        body+=chunk;
        if(Buffer.byteLength(body)>16000)
            throw new HttpError(413,'Request too large')}
    let input:unknown;
    try{input=JSON.parse(body)}
    catch{
        throw new HttpError(400,'Invalid JSON')}
    if(path==='/api/reviews')
    {
        const p=requestSchema.parse(input);
            return send(201,await service.start(p.claimId,p.requestId)
        )
    }
    const m=path.match(/^\/api\/reviews\/([a-f0-9-]+)\/decision$/)
    if(m){const p=reviewSchema.parse(input);return send(200,await service.review(m[1],p.decision,p.requestId))}
   }
   throw new HttpError(404,'Endpoint not found')
  }
  if(req.method!=='GET')
    throw new HttpError(405,'Method not allowed')
  const file=path==='/'?resolve(dist,'index.html'):resolve(dist,'.'+path)
  if(!file.startsWith(dist+'/'))
    throw new HttpError(404,'Not found')
  try{
    const data=await readFile(file);
    res.writeHead(200,{'Content-Type':mime[extname(file)]??'application/octet-stream'});res.end(data)}catch{throw new HttpError(404,'Build the UI with npm run build, or open the Vite URL on port 4317')}
 }catch(e){send(e instanceof HttpError?e.status:e instanceof ZodError?400:500,{error:e instanceof HttpError?e.message:e instanceof ZodError?'Invalid request fields':'Internal error'})}
})

server.listen(4318,'127.0.0.1',()=>console.log('GEHA backend: http://127.0.0.1:4318'))
