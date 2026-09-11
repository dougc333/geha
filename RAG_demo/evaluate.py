"""Retrieval checks are offline after model download. Generation is opt-in."""
import argparse
import json
import os
from datetime import datetime, timezone
from rag import ROOT, Retriever, build_graph

def run_evals(retriever, generate=False, base_url='',model='',api_key=''):
    graph=build_graph(retriever,base_url,model,api_key,generate)
    results=[]
    for case in json.loads((ROOT/'evals/cases.json').read_text()):
        # No reference answers are ever passed to retrieval or generation.
        state=graph.invoke({'question':case['question'],'document':'all'})
        expected=[c for c in state['chunks'] if c['metadata']['document_id']==case['document'] and c['metadata']['page']==case['page']]
        evidence=' '.join(c['text'] for c in expected).lower()
        hit=bool(expected) and all(term.lower() in evidence for term in case['required_terms']) if case['answerable'] else None
        results.append({'id':case['id'],'question':case['question'],'reference':case['reference'],'answerable':case['answerable'],'retrieval_pass':hit,'answer':state['answer'] if generate else None,'abstention_pass':state['abstained']==(not case['answerable']) if generate else None,'citation_ids':[c['id'] for c in state['citations']],'retrieved_ids':[c['id'] for c in state['chunks']]})
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--generate',action='store_true')
    args=parser.parse_args()
    rows=run_evals(Retriever(),args.generate,os.getenv('MODEL_BASE_URL','http://localhost:11434/v1'),os.getenv('MODEL_NAME','llama3.2:3b'),os.getenv('MODEL_API_KEY',''))
    folder=ROOT/'results'; folder.mkdir(exist_ok=True)
    path=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
    path.write_text(json.dumps(rows,indent=2)+'\n')
    graded=[r for r in rows if r['retrieval_pass'] is not None]
    print(f'Retrieval evidence checks: {sum(r["retrieval_pass"] for r in graded)}/{len(graded)}')
    print('Answer correctness requires review; retrieval success does not prove answer accuracy.')
    print(path)
