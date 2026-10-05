import unittest
from corpus_search import select_retrieval_mode


class QueryRoutingTests(unittest.TestCase):
    def test_exact_codes(self):
        for query in ['Is D1110 covered?', 'What about d2740?', 'Compare D1110 and D1120.']:
            self.assertEqual(select_retrieval_mode(query), 'bm25')

    def test_natural_language_and_non_codes(self):
        for query in ['How many cleanings?', 'My child is 23', '2026 benefits', 'D11100', 'AD1110']:
            self.assertEqual(select_retrieval_mode(query), 'vector')


if __name__ == '__main__':
    unittest.main()
