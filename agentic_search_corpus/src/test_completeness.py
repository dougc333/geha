import unittest
from test_agentic_rag import client, agent


class CompletenessTests(unittest.TestCase):
    def test_missing_evidence_triggers_search_and_accumulates(self):
        c = client()
        answers = iter([{'complete': False, 'missing': ['deadline'], 'next_query': 'QLE deadline'},
                        {'complete': True, 'missing': [], 'next_query': ''}])
        result = agent(c, completeness=lambda q, ctx: next(answers)).generate('married')
        self.assertEqual(c.retriever.queries, ['married', 'QLE deadline'])
        self.assertIn('passage about married', result['contexts'])
        self.assertIn('passage about QLE deadline', result['contexts'])
        self.assertTrue(result['complete'])

    def test_followups_bounded_and_unresolved_visible(self):
        c = client()
        result = agent(c, completeness=lambda q, ctx: {
            'complete': False, 'missing': ['deadline'], 'next_query': 'next ' + str(len(c.retriever.queries))}).generate('q')
        self.assertEqual(len(c.retriever.queries), 2)
        self.assertFalse(result['complete'])
        self.assertIn('Evidence remains incomplete', result['response'])

    def test_repeated_query_stops(self):
        c = client()
        result = agent(c, completeness=lambda q, ctx: {'complete': False, 'missing': ['rule'], 'next_query': 'Q'}).generate('q')
        self.assertEqual(c.retriever.queries, ['q'])
        self.assertFalse(result['complete'])

    def test_complete_does_not_search_again(self):
        c = client()
        result = agent(c, completeness=lambda q, ctx: {'complete': True}).generate('q')
        self.assertEqual(c.retriever.queries, ['q'])
        self.assertTrue(result['complete'])

    def test_duplicate_evidence_deduplicated(self):
        c = client()
        c.reranker.rerank = lambda *a, **kw: ['same passage']
        replies = iter([{'complete': False, 'missing': ['rule'], 'next_query': 'another'}, {'complete': True}])
        result = agent(c, completeness=lambda q, ctx: next(replies)).generate('q')
        self.assertEqual(result['retrieved_contexts'], ['same passage'])


if __name__ == '__main__':
    unittest.main()
