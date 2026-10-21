import unittest

from rag_core import bm25_rank, chunk_text, reciprocal_rank_fusion


ROWS = [
    {"id": 1, "chunk_index": 0, "content": "alpha beta beta", "page": 1},
    {"id": 2, "chunk_index": 1, "content": "alpha gamma", "page": 1},
    {"id": 3, "chunk_index": 2, "content": "unrelated", "page": 2},
]


class RagCoreTests(unittest.TestCase):
    def test_bm25_ranks_matching_frequency_first(self):
        ranked = bm25_rank("beta", ROWS)
        self.assertEqual([row["id"] for row in ranked], [1, 2, 3])
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])

    def test_rrf_rewards_results_present_in_both_lists(self):
        vector = [{**ROWS[0], "score": .9}, {**ROWS[1], "score": .8}]
        lexical = [{**ROWS[1], "score": 4.0}, {**ROWS[2], "score": 2.0}]
        ranked = reciprocal_rank_fusion([vector, lexical])
        self.assertEqual(ranked[0]["id"], 2)

    def test_chunking_has_overlap(self):
        chunks = chunk_text("one two three four five", size=3, overlap=1)
        self.assertEqual(chunks, ["one two three", "three four five", "five"])


if __name__ == "__main__":
    unittest.main()
