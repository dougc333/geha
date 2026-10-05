"""Run the existing six-question benchmark using MiMo-V2.5 via Nous.

Separate checkpoints; same corpus, questions, prompts and graph as Gemma.
"""
import json
import os
import statistics
import time
import urllib.error
import urllib.request
import gemma_answer_benchmark as bench

MODEL = 'xiaomi/mimo-v2.5'
bench.MODEL = MODEL
bench.OUT = bench.ROOT / 'evals/mimo_nous_answers.jsonl'


class Nous:
    def __init__(self):
        self.key = os.getenv('NOUS_API_KEY') or os.getenv('NOUS_KEY')
        if not self.key:
            raise ValueError('Missing NOUS_API_KEY or NOUS_KEY')
        self.calls = []

    def ask(self, prompt, task, json_output=False):
        payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}],
                   'temperature': 0, 'max_tokens': 2500}
        if json_output:
            payload['response_format'] = {'type': 'json_object'}
        started = time.perf_counter()
        for attempt in range(6):
            try:
                req = urllib.request.Request(
                    'https://inference-api.nousresearch.com/v1/chat/completions',
                    data=json.dumps(payload).encode(), headers={
                        'Authorization': 'Bearer ' + self.key,
                        'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=100) as response:
                    data = json.load(response)
                text = data['choices'][0]['message']['content']
                usage = data.get('usage', {})
                self.calls.append({'task': task, 'seconds': time.perf_counter()-started,
                                   'usage': usage})
                if not text:
                    raise ValueError('Empty Nous response')
                return bench.parse_object(text) if json_output else text
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(45, 3 * 2**attempt))
                    continue
                raise RuntimeError('Nous HTTP ' + str(exc.code)) from None
        raise RuntimeError('Nous retries exhausted')


bench.Google = Nous


def report():
    latest = {}
    for line in bench.OUT.read_text().splitlines():
        row = json.loads(line)
        latest[row['id'], row['mode'], row['workflow']] = row
    rows = list(latest.values())
    lines = ['# MiMo-V2.5 via Nous dental benchmark', '',
             'Same six questions, corpus, answer prompt and bounded graph as Gemma.',
             'MiMo judges its own answers; scores are not human-validated accuracy.',
             'JSON-object output is validated locally; unlike Google, no response schema is sent.',
             'Sequential calls without the Google-specific 14-second delay; retries included in latency.', '',
             '| Retrieval | Workflow | Completed | Rubric completeness | Supported citations | Median seconds |',
             '|---|---|---:|---:|---:|---:|']
    for mode in ['bm25', 'vector', 'hybrid']:
        for workflow in ['one_pass', 'agentic']:
            group = [r for r in rows if r['mode']==mode and r['workflow']==workflow and 'completeness' in r]
            if group:
                lines.append(f"| {mode} | {workflow} | {len(group)}/6 | {statistics.mean(r['completeness'] for r in group):.1%} | {sum(r['judgment']['citations_supported'] is True for r in group)}/{len(group)} | {statistics.median(r['seconds'] for r in group):.1f} |")
    lines += ['', f"Completed: {sum('completeness' in r for r in rows)}/36; errors: {sum('error' in r for r in rows)}.",
              'Paid Nous inference; full usage metadata saved in mimo_nous_answers.jsonl.',
              'Cross-model self-judging and different pacing confound comparisons with Gemma.']
    (bench.ROOT/'evals/mimo_nous_results.md').write_text('\n'.join(lines)+'\n')
    print(lines[-3], flush=True)


def main():
    Nous()  # Check credentials before loading embeddings.
    search = bench.CorpusSearch()
    search.load_vectors()
    done = set()
    if bench.OUT.exists():
        done = {(r['id'], r['mode'], r['workflow']) for r in map(json.loads, bench.OUT.read_text().splitlines()) if 'completeness' in r}
    for case in bench.CASES:
        for mode in ['bm25', 'vector', 'hybrid']:
            for workflow in ['one_pass', 'agentic']:
                if (case['id'], mode, workflow) in done:
                    continue
                row = bench.run(search, case, mode, workflow)
                report()
                if row.get('error', '').startswith('RuntimeError: Nous HTTP'):
                    raise RuntimeError(row['error'])


if __name__ == '__main__':
    main()
