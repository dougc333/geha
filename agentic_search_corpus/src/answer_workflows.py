"""Two vector-backed answer workflows; no implicit BM25 routing."""
from corpus_search import make_agent

SINGLE = 'Vector search single-turn agent'
MULTI = 'Multiturn agent'
OPTIONS = [SINGLE, MULTI]


class VectorRetriever:
    def __init__(self, search):
        self.search = search

    def invoke(self, query):
        return self.search.search(query, mode='vector')


def answer_question(search, question, workflow, agent_factory=make_agent):
    if workflow not in OPTIONS:
        raise ValueError('Unknown answer workflow')
    retriever = VectorRetriever(search)
    if workflow == MULTI:
        result = agent_factory(retriever).generate(question)
        return {'role': 'assistant', 'content': result['response'],
                'trace': result['trace'], 'grounded': result['grounded'],
                'complete': result.get('complete'), 'missing': result.get('missing', []),
                'evidence': [result['contexts']]}
    docs = retriever.invoke(question)
    evidence = [f"[{d.metadata['chunk_id']}]\n{d.page_content}" for d in docs]
    if evidence:
        client = agent_factory(retriever).client
        response = client.chain.invoke({'question': question, 'context': client.format_context(evidence)})
    else:
        response = 'I could not find this in the documents.'
    return {'role': 'assistant', 'content': response, 'evidence': evidence,
            'trace': ['retrieve once (vector)', 'generate once' if evidence else 'no matching evidence']}
