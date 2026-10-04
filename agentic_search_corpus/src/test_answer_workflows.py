import unittest
from types import SimpleNamespace
from answer_workflows import answer_question, SINGLE, MULTI


class WorkflowTests(unittest.TestCase):
    def test_single_uses_vector_even_for_code_and_one_generation(self):
        searches, generations = [], []
        doc = SimpleNamespace(metadata={'chunk_id': 'page-010.md'}, page_content='evidence')
        search = SimpleNamespace(search=lambda q, mode: searches.append((q, mode)) or [doc])
        client = SimpleNamespace(format_context=lambda x: '\n'.join(x),
                                 chain=SimpleNamespace(invoke=lambda x: generations.append(x) or 'answer'))
        result = answer_question(search, 'D1110', SINGLE, lambda r: SimpleNamespace(client=client))
        self.assertEqual(searches, [('D1110', 'vector')])
        self.assertEqual(len(generations), 1)
        self.assertEqual(result['content'], 'answer')

    def test_multi_delegates_to_graph_and_exposes_missing_evidence(self):
        searches = []
        search = SimpleNamespace(search=lambda q, mode: searches.append(mode) or [])
        def factory(retriever):
            def generate(q):
                retriever.invoke(q)
                return {'response': 'partial', 'trace': ['completeness: incomplete'],
                        'grounded': True, 'complete': False, 'missing': ['deadline'], 'contexts': 'evidence'}
            return SimpleNamespace(generate=generate)
        result = answer_question(search, 'q', MULTI, factory)
        self.assertEqual(searches, ['vector'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['missing'], ['deadline'])

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            answer_question(None, 'q', 'invalid')
