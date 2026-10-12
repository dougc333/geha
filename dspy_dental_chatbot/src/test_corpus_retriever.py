"""Integration tests for the existing Docling hybrid corpus adapter."""

from __future__ import annotations

import unittest

from corpus_retriever import ExistingDentalCorpusRetriever


class ExistingDentalCorpusRetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = ExistingDentalCorpusRetriever(include_plan_brochure=False)

    def test_bm25_retrieves_docling_vision_table(self):
        hits = self.retriever.search(
            "vision glasses eye exam frames retail price",
            mode="bm25",
            top_k=4,
        )

        self.assertEqual(hits[0].page, 7)
        self.assertIn("Frames", hits[0].text)
        self.assertIn("60% of retail price", hits[0].text)

    def test_guide_only_scope_excludes_plan_brochure(self):
        hits = self.retriever.search("new federal employee enrollment", mode="bm25", top_k=4)

        self.assertTrue(
            all(hit.document.endswith("2026-geha-dental-benefits-guide") for hit in hits)
        )

    def test_policy_adapter_expands_retailer_and_glasses_terms(self):
        chunks = self.retriever.search_policy_chunks(
            "Are my Walmart glasses covered?",
            mode="bm25",
            top_k=4,
        )

        self.assertEqual(chunks[0].page, 7)
        self.assertIn("Frames", chunks[0].text)

    def test_auto_mode_routes_dental_code_to_bm25_across_both_documents(self):
        retriever = ExistingDentalCorpusRetriever(include_plan_brochure=True)
        chunks = retriever.search_policy_chunks(
            "D7140 extraction High Standard in-network",
            mode="auto",
            top_k=6,
        )
        pages = {chunk.page for chunk in chunks}

        self.assertIn(26, pages)
        self.assertTrue(pages.intersection({5, 23}))

    def test_verbose_code_queries_keep_exact_and_cost_sharing_pages(self):
        retriever = ExistingDentalCorpusRetriever(include_plan_brochure=True)
        cases = [
            (
                "My dentist put CDT code D1110 on the estimate. How many adult "
                "cleanings do High and Standard cover each calendar year, and what "
                "is the in-network member cost?",
                [{21}, {5, 20}],
            ),
            (
                "For root canal code D3310, is there a lifetime restriction and what "
                "do High and Standard members pay in-network?",
                [{29}, {5, 28}],
            ),
        ]

        for query, required_groups in cases:
            with self.subTest(query=query):
                pages = {
                    chunk.page
                    for chunk in retriever.search_policy_chunks(
                        query,
                        mode="auto",
                        top_k=6,
                    )
                }
                self.assertTrue(all(pages.intersection(group) for group in required_groups))

    def test_code_results_start_with_definition_and_benefit_comparison(self):
        retriever = ExistingDentalCorpusRetriever(include_plan_brochure=True)

        for code, expected_definition_page in [("D1110", 21), ("D7140", 26), ("D3310", 29)]:
            with self.subTest(code=code):
                chunks = retriever.search_policy_chunks(
                    f"What does {code} cost under High versus Standard?",
                    mode="auto",
                    top_k=6,
                )
                self.assertEqual([chunk.page for chunk in chunks[:2]], [expected_definition_page, 5])

    def test_code_results_exclude_unrelated_class_pages_when_canonical_sources_exist(self):
        retriever = ExistingDentalCorpusRetriever(include_plan_brochure=True)

        cases = {
            "D1110": [21, 5],
            "D7140": [26, 5],
            "D3310": [29, 5],
        }
        for code, expected_pages in cases.items():
            with self.subTest(code=code):
                chunks = retriever.search_policy_chunks(
                    f"What does {code} cost under High versus Standard?",
                    mode="auto",
                    top_k=6,
                )
                self.assertEqual([chunk.page for chunk in chunks], expected_pages)

    def test_d1110_definition_beats_incidental_code_reference(self):
        retriever = ExistingDentalCorpusRetriever(include_plan_brochure=True)

        chunks = retriever.search_policy_chunks(
            "How many D1110 adult cleanings are covered?",
            mode="auto",
            top_k=6,
        )

        self.assertEqual(chunks[0].page, 21)
        self.assertIn("D1110 Prophylaxis - adult", chunks[0].text)
        self.assertNotEqual(chunks[0].page, 35)


if __name__ == "__main__":
    unittest.main()
