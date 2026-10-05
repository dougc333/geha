"""Compare retrieval modes on identical page-level evidence labels; no LLM calls."""
import json
import sys
import time
from pathlib import Path
import statistics
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from corpus_search import CorpusSearch

def main():
    questions = [json.loads(line) for line in (ROOT / 'evals/queries.jsonl').read_text().splitlines() if line.strip()]
    search = CorpusSearch()
    started = time.perf_counter()
    search.load_vectors()
    setup = time.perf_counter() - started
    rows = []
    for q in questions:
        for mode in ['bm25', 'vector', 'hybrid']:
            started = time.perf_counter()
            docs = search.search(q['query'], top_k=10, mode=mode)
            latency = (time.perf_counter() - started) * 1000
            ids = [d.metadata['chunk_id'] for d in docs]
            gold = set(q['evidence'])
            for item in gold:
                if item not in {d.metadata['chunk_id'] for d in search.docs}:
                    raise ValueError('Unknown evidence label: ' + item)
            rank = next((i for i, item in enumerate(ids, 1) if item in gold), None)
            rows.append({'id': q['id'], 'query': q['query'], 'mode': mode,
                         'recall@5': len(gold.intersection(ids[:5])) / len(gold),
                         'all_evidence@5': gold.issubset(ids[:5]),
                         'mrr@10': 1 / rank if rank else 0,
                         'latency_ms': latency, 'retrieved': ids, 'evidence': sorted(gold)})
    summary = {}
    for mode in ['bm25', 'vector', 'hybrid']:
        subset = [r for r in rows if r['mode'] == mode]
        summary[mode] = {metric: statistics.mean(r[metric] for r in subset)
                         for metric in ['recall@5', 'all_evidence@5', 'mrr@10']}
        summary[mode]['median_latency_ms'] = statistics.median(r['latency_ms'] for r in subset)
    report = {'pages': len(search.docs), 'setup_seconds': setup, 'summary': summary, 'rows': rows}
    (ROOT / 'evals/results.json').write_text(json.dumps(report, indent=2))
    lines = ['# Dental corpus retrieval comparison', '',
             f'{len(questions)} questions; {len(search.docs)} Markdown pages; BGE large; setup {setup:.1f}s.', '',
             '| Mode | Evidence Recall@5 | All evidence@5 | MRR@10 | Median query ms |',
             '|---|---:|---:|---:|---:|']
    for mode, values in summary.items():
        lines.append(f"| {mode} | {values['recall@5']:.3f} | {values['all_evidence@5']:.3f} | {values['mrr@10']:.3f} | {values['median_latency_ms']:.1f} |")
    lines += ['', 'These are curated page-level retrieval labels, not answer-accuracy or agentic-loop scores.',
              'Multi-page labels require all listed pages; alternative valid evidence is not exhaustively labeled.',
              'Single local run, sequential modes; setup excluded from query latency. No OpenAI calls.', '', '## Example questions', '']
    lines += [f"- {q['query']}" for q in questions]
    (ROOT / 'evals/results.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:12]))

if __name__ == '__main__':
    main()
