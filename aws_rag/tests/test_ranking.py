"""Reciprocal-rank fusion and BM25 (query/rag_core.py) and the eval's answer matching."""

import unittest

from support import load

rag_core = load("query_rag_core", "query/rag_core.py")
answer_check = load("answer_check", "evals/answer_check.py")


def row(chunk_id: int, content: str = "") -> dict:
    return {"id": chunk_id, "chunk_index": chunk_id, "content": content}


class ReciprocalRankFusionTest(unittest.TestCase):
    def test_found_by_both_beats_found_by_one(self):
        vector = [row(1), row(2), row(3)]
        keyword = [row(3), row(4)]
        fused = rag_core.reciprocal_rank_fusion([vector, keyword])
        self.assertEqual(fused[0]["id"], 3)
        self.assertEqual({r["id"] for r in fused}, {1, 2, 3, 4})
        self.assertAlmostEqual(fused[0]["score"], 1 / 63 + 1 / 61)

    def test_weights(self):
        fused = rag_core.reciprocal_rank_fusion([[row(1)], [row(2)]], weights=[2.0, 1.0])
        self.assertEqual([r["id"] for r in fused], [1, 2])

    def test_ties_break_by_chunk_index(self):
        fused = rag_core.reciprocal_rank_fusion([[row(5)], [row(2)]])
        self.assertEqual([r["id"] for r in fused], [2, 5])

    def test_empty(self):
        self.assertEqual(rag_core.reciprocal_rank_fusion([[], []]), [])


class Bm25Test(unittest.TestCase):
    def test_rare_term_outranks_common_term(self):
        rows = [row(1, "the model uses attention"), row(2, "the model uses dropout"),
                row(3, "the model uses attention and dropout")]
        ranked = rag_core.bm25_rank("attention", rows)
        self.assertEqual({r["id"] for r in ranked[:2]}, {1, 3})
        self.assertEqual(ranked[-1]["score"], 0.0)

    def test_tokenize_keeps_hyphenated_words(self):
        self.assertEqual(rag_core.tokenize("BERT-Large, top-5 error!"), ["bert-large", "top-5", "error"])


class AnswerNormTest(unittest.TestCase):
    """answer_check counts an answer correct when norm(gold) is in norm(answer)."""

    def contains(self, gold: str, answer: str) -> bool:
        return answer_check.norm(gold) in answer_check.norm(answer)

    def test_ignores_percent_trailing_zeros_commas_and_spaces(self):
        self.assertTrue(self.contains("86.6", "BERT-Large reaches 86.60% on SWAG."))
        self.assertTrue(self.contains("1000", "about 1,000 examples"))
        self.assertTrue(self.contains("{0.001, 0.003}", "{ 0.001, 0.003 }"))
        self.assertTrue(self.contains("PixelNorm", "a pixelnorm layer"))

    def test_different_numbers_do_not_match(self):
        self.assertFalse(self.contains("86.6", "86.3"))
        self.assertFalse(self.contains("85.2", "78.6"))


if __name__ == "__main__":
    unittest.main()
