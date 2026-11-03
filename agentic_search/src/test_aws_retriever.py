"""AWS retriever and Nova decision tests; no network or AWS calls."""

import io
import json
import unittest

from aws_retriever import AwsCitationReranker, AwsRagRetriever, BedrockNova


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AwsRetrieverTest(unittest.TestCase):
    def test_invoke_preserves_multimodal_citation_metadata(self):
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response(json.dumps({"results": [{
                "paper": {"title": "YOLO", "document_id": "doc-1"},
                "page": 6, "chunk_id": 42, "chunk_index": 9,
                "content_type": "figure", "content": "Loc: 19.0%",
                "citation_metadata": {"figure_id": "p006_f01", "bbox": [1, 2, 3, 4]},
                "image_key": "figures/doc-1/p006_f01.png", "image_url": "https://signed/image",
                "rerank_score": 0.91,
            }]}).encode())

        retriever = AwsRagRetriever("https://example.test/", "secret", opener=open_request)
        docs = retriever.invoke("YOLO localization error")
        self.assertEqual(captured["request"].full_url, "https://example.test/api/retrieve")
        self.assertEqual(captured["request"].get_header("X-api-key"), "secret")
        self.assertEqual(docs[0].page_content, "Loc: 19.0%")
        self.assertEqual(docs[0].metadata["citation_metadata"]["figure_id"], "p006_f01")
        passage = AwsCitationReranker.rerank(docs, "q")[0]
        self.assertIn("paper=YOLO; page=6; chunk=42; type=figure; figure=p006_f01", passage)
        self.assertEqual(passage.metadata["image_key"], "figures/doc-1/p006_f01.png")


class FakeBedrock:
    def __init__(self, texts):
        self.texts = iter(texts)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": next(self.texts)}]}}}


class BedrockNovaTest(unittest.TestCase):
    def test_assesses_all_passages_in_one_call(self):
        bedrock = FakeBedrock(['{"relevant_indices":[1,3],"complete":false,'
                               '"missing":["Self-RAG"],"next_query":"Self-RAG retrieval tokens"}'])
        nova = BedrockNova(client=bedrock)
        result = nova.assess("compare", "RAG", ["one", "two", "three"], [])
        self.assertEqual(result["relevant_indices"], [1, 3])
        self.assertEqual(result["next_query"], "Self-RAG retrieval tokens")
        self.assertEqual(len(bedrock.calls), 1)
        prompt = bedrock.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn("[1] one", prompt)
        self.assertIn("[3] three", prompt)

    def test_grounding_uses_nova_json_decision(self):
        bedrock = FakeBedrock(['prefix {"grounded": true} suffix'])
        citation = "[paper=YOLO; page=6; chunk=42; type=figure]"
        self.assertTrue(BedrockNova(client=bedrock).grounded(
            f"{citation}\nevidence", f"answer {citation}"
        ))

    def test_grounding_rejects_answer_without_retrieved_citation(self):
        bedrock = FakeBedrock([])
        citation = "[paper=YOLO; page=6; chunk=42; type=figure]"
        self.assertFalse(BedrockNova(client=bedrock).grounded(f"{citation}\nevidence", "answer"))
        self.assertEqual(bedrock.calls, [])

    def test_answer_strips_urls_and_unknown_citations(self):
        bedrock = FakeBedrock([
            "Claim [paper=YOLO; page=6; chunk=42; type=figure](https://example.com/x). "
            "Bad [paper=Invented; page=1; chunk=999](https://example.com/y)."
        ])
        context = "[paper=YOLO; page=6; chunk=42; type=figure]\nLoc: 19.0%"
        answer = BedrockNova(client=bedrock).answer("q", context)
        self.assertIn("[paper=YOLO; page=6; chunk=42; type=figure]", answer)
        self.assertNotIn("example.com", answer)
        self.assertNotIn("paper=Invented", answer)

    def test_answer_expands_short_citation_to_exact_context_label(self):
        bedrock = FakeBedrock([
            "Claim [paper=YOLO; page=6; chunk=42](https://example.com/x)."
        ])
        context = "[paper=YOLO; page=6; chunk=42; type=figure; figure=p006_f01]\nLoc: 19.0%"
        answer = BedrockNova(client=bedrock).answer("q", context)
        self.assertIn(
            "[paper=YOLO; page=6; chunk=42; type=figure; figure=p006_f01]", answer
        )
        self.assertNotIn("example.com", answer)

    def test_revision_prompt_contains_previous_answer(self):
        bedrock = FakeBedrock(["revised"])
        BedrockNova(client=bedrock).answer("q", "evidence", "old answer", "remove unsupported claims")
        prompt = bedrock.calls[0]["messages"][0]["content"][0]["text"]
        self.assertIn("PREVIOUS ANSWER:\nold answer", prompt)
        self.assertIn("remove unsupported claims", prompt)

    def test_scores_gold_facts_in_one_batched_call(self):
        bedrock = FakeBedrock(['{"supported_indices":[3,1,99,1]}'])
        result = BedrockNova(client=bedrock).score_facts(
            "question", "answer", ["fact one", "fact two", "fact three"]
        )
        self.assertEqual(result, [1, 3])
        self.assertEqual(len(bedrock.calls), 1)


if __name__ == "__main__":
    unittest.main()
