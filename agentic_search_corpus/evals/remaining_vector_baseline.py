"""Finish unscored Gemma vector/one-pass cases without resuming other modes."""
import json
import gemma_answer_benchmark as bench


if __name__ == '__main__':
    bench.Google()
    done = set()
    if bench.OUT.exists():
        done = {r['id'] for r in map(json.loads, bench.OUT.read_text().splitlines())
                if r['mode'] == 'vector' and r['workflow'] == 'one_pass' and 'completeness' in r}
    search = bench.CorpusSearch()
    search.load_vectors()
    for case in bench.CASES:
        if case['id'] not in done:
            bench.run(search, case, 'vector', 'one_pass')
            bench.report()
