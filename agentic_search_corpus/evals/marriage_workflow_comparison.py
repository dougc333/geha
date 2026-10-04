"""Live comparison of the two UI backends on one question. No LLM evaluator."""
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from corpus_search import CorpusSearch
from answer_workflows import OPTIONS, answer_question

QUESTION = 'I just got married and want to add my spouse. Can I switch from Standard to High at the same time, and how long do I have?'


class Calls(BaseCallbackHandler):
    def __init__(self):
        self.count = 0
    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.count += 1


if __name__ == '__main__':
    load_dotenv(ROOT/'.env', override=False)
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY missing')
    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.config import var_child_runnable_config
    search = CorpusSearch()
    start = time.perf_counter()
    search.load_vectors()
    setup = time.perf_counter()-start
    output = ROOT/'evals/marriage_workflow_comparison.jsonl'
    for workflow in OPTIONS:
        callback = Calls()
        token = var_child_runnable_config.set(RunnableConfig(callbacks=[callback]))
        start = time.perf_counter()
        try:
            result = answer_question(search, QUESTION, workflow)
            result.update(query=QUESTION, workflow=workflow, model='gpt-4o',
                          seconds=time.perf_counter()-start, llm_calls=callback.count,
                          setup_seconds_excluded=setup)
        finally:
            var_child_runnable_config.reset(token)
        with output.open('a') as handle:
            handle.write(json.dumps(result)+'\n')
        print(json.dumps({k:result[k] for k in ['workflow','seconds','llm_calls','content','trace']},indent=2),flush=True)
