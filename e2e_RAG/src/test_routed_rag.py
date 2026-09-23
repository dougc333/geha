import tempfile
import unittest
from pathlib import Path

import pymupdf
from langchain_core.documents import Document

from routed_rag import (
    RAGConfig,
    RoutedRAG,
    build_parent_child_documents,
    calculate_token_cost,
    chunk_pages,
    extract_usage_metadata,
    load_pdf,
    reciprocal_rank_fusion,
    route_query,
)


class RoutedRAGUnitTests(unittest.TestCase):
    def test_manual_route_wins(self):
        strategy, reason = route_query("J9033 approval criteria", "vector")
        self.assertEqual(strategy, "vector")
        self.assertIn("selected", reason)

    def test_deterministic_routes(self):
        cases = {
            "What does J9033 cover?": "hybrid",
            "How was FLAN-v2 sampled?": "hybrid",
            'Find the phrase "teaching assistant"': "hybrid",
            "Show the complete approval criteria": "parent_child",
            "Compare the documented approaches": "query_expansion",
            "orca": "hyde",
            "What is instruction tuning in this paper?": "vector",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(route_query(query)[0], expected)

    def test_rrf_deduplicates_and_rewards_multiple_lists(self):
        a = Document(page_content="a", metadata={"chunk_id": "a"})
        b = Document(page_content="b", metadata={"chunk_id": "b"})
        c = Document(page_content="c", metadata={"chunk_id": "c"})
        result = reciprocal_rank_fusion([[a, b], [b, c]], final_k=3)
        self.assertEqual([doc.metadata["chunk_id"] for doc in result], ["b", "a", "c"])

    def test_rrf_merges_retrieval_channels(self):
        vector = Document(
            page_content="same",
            metadata={
                "chunk_id": "x",
                "retrieval_channels": ["vector"],
                "retrieval_queries": ["q"],
            },
        )
        bm25 = Document(
            page_content="same",
            metadata={
                "chunk_id": "x",
                "retrieval_channels": ["bm25"],
                "retrieval_queries": ["q"],
            },
        )
        result = reciprocal_rank_fusion([[vector], [bm25]], final_k=1)
        self.assertEqual(result[0].metadata["retrieval_channels"], ["vector", "bm25"])

    def test_pdf_load_and_parent_child_links(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            pdf = pymupdf.open()
            for text in ("Page one coverage criteria.", "Page two billing code J9033."):
                page = pdf.new_page()
                page.insert_text((72, 72), text)
            pdf.save(path)
            pdf.close()

            pages = load_pdf(path)
            self.assertEqual(len(pages), 2)
            self.assertEqual(pages[1].metadata["page"], 2)

            chunks = chunk_pages(pages, chunk_size=20, chunk_overlap=2)
            self.assertTrue(chunks)
            self.assertTrue(all("chunk_id" in doc.metadata for doc in chunks))

            parents, children, by_id = build_parent_child_documents(
                pages, parent_size=30, child_size=10
            )
            self.assertTrue(parents)
            self.assertTrue(children)
            self.assertTrue(
                all(child.metadata["parent_id"] in by_id for child in children)
            )

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            RAGConfig(child_size=900, parent_size=900).validate()

    def test_reranker_cost_calculation(self):
        cost = calculate_token_cost(
            input_tokens=1_000,
            cached_input_tokens=200,
            output_tokens=100,
            input_cost_per_million=2.00,
            cached_input_cost_per_million=0.50,
            output_cost_per_million=8.00,
        )
        self.assertAlmostEqual(cost["input_cost_usd"], 0.0017)
        self.assertAlmostEqual(cost["output_cost_usd"], 0.0008)
        self.assertAlmostEqual(cost["total_cost_usd"], 0.0025)

    def test_usage_metadata_normalization(self):
        class Message:
            usage_metadata = {
                "input_tokens": 541,
                "output_tokens": 37,
                "total_tokens": 578,
                "input_token_details": {"cache_read": 100},
            }
            response_metadata = {}

        self.assertEqual(
            extract_usage_metadata(Message()),
            {
                "input_tokens": 541,
                "cached_input_tokens": 100,
                "output_tokens": 37,
                "total_tokens": 578,
            },
        )

    def test_reset_deletes_both_indexes(self):
        class FakeStore:
            def __init__(self):
                self.deleted = False

            def delete_collection(self):
                self.deleted = True

        engine = RoutedRAG.__new__(RoutedRAG)
        engine.vectorstore = FakeStore()
        engine.child_vectorstore = FakeStore()
        engine.reset_indexes()

        self.assertTrue(engine.vectorstore.deleted)
        self.assertTrue(engine.child_vectorstore.deleted)


if __name__ == "__main__":
    unittest.main()
