"""Unit tests for the class-based CLI refactor.

These tests use injected fakes and do not require an API key, a PDF download,
an embedding model, or a running Streamlit server.
"""

import unittest
from types import SimpleNamespace

from app_class import CliApplication
from app_streamlit_class import StreamlitApplication
from rag_client_class import RagClient
from reranking_models_class import RerankingModels


class FakeChain:
    def invoke(self, values):
        return f"answer:{values['question']}|{values['context']}"

    def stream(self, values):
        yield "answer:"
        yield values["question"]


class FakeRetriever:
    def invoke(self, query):
        return [
            SimpleNamespace(page_content=f"evidence for {query} one", metadata={"rank": 1}),
            SimpleNamespace(page_content=f"evidence for {query} two", metadata={"rank": 2}),
        ]


class FakeReranker:
    def rerank(self, documents, query, model="gpt"):
        assert query
        return [doc.page_content.upper() for doc in documents]


class FakeClient:
    def __init__(self):
        self.chain = FakeChain()
        self.retriever = FakeRetriever()
        self.reranker = FakeReranker()

    def retrieve_context_reranked(self, query, reranker_model="gpt"):
        docs = self.retriever.invoke(query)
        return self.reranker.rerank(docs, query, reranker_model)

    @staticmethod
    def format_context(contexts, limit=3):
        return "\n".join(list(contexts)[:limit])

    def stream(self, query, reranker_model="gpt"):
        context = self.format_context(self.retrieve_context_reranked(query, reranker_model))
        yield from self.chain.stream({"context": context, "question": query})


class ClassRefactorTests(unittest.TestCase):
    def test_streamlit_pdf_preview_uses_selected_upload_bytes(self):
        rendered = []

        class FakeStreamlit:
            @staticmethod
            def markdown(*args, **kwargs):
                rendered.append((args, kwargs))

            @staticmethod
            def pdf(value, **kwargs):
                rendered.append(("pdf", value, kwargs))

        selected_file = SimpleNamespace(getvalue=lambda: b"selected-pdf-bytes")
        StreamlitApplication.display_pdf(FakeStreamlit, selected_file)

        pdf_render = next(item for item in rendered if item[0] == "pdf")
        self.assertEqual(pdf_render[1], b"selected-pdf-bytes")
        self.assertTrue(pdf_render[2]["key"].startswith("pdf-preview-"))

    def test_reranker_passthrough_preserves_document_text(self):
        model = RerankingModels()
        docs = [SimpleNamespace(page_content="one"), SimpleNamespace(page_content="two")]
        self.assertEqual(model.rerank(docs, "question", model="none"), ["one", "two"])

    def test_rag_client_context_and_generation_with_injected_dependencies(self):
        client = RagClient.__new__(RagClient)
        client.retriever = FakeRetriever()
        client.reranker = FakeReranker()
        client.chain = FakeChain()
        self.assertEqual(client.format_context(["a", "b", "c", "d"]), "a\nb\nc")
        result = client.generate("instruction tuning", reranker_model="none")
        self.assertIn("instruction tuning", result["response"])
        self.assertIn("EVIDENCE FOR", result["contexts"])

    def test_cli_answer_uses_client_and_returns_text(self):
        app = CliApplication.__new__(CliApplication)
        app.client = FakeClient()
        answer = app.answer("What is RAG?", reranker_model="none")
        self.assertIn("What is RAG?", answer)
        self.assertIn("EVIDENCE FOR WHAT IS RAG?", answer)

    def test_cli_run_stops_on_exit(self):
        app = CliApplication.__new__(CliApplication)
        app.client = FakeClient()
        inputs = iter(["What is RAG?", "exit"])
        output = []
        app.run(input_fn=lambda _: next(inputs), output_fn=lambda *args, **kwargs: output.append(args[0] if args else ""))
        self.assertTrue(any("LLM Response" in item for item in output))

    def test_cli_prints_complete_response_before_requesting_next_input(self):
        app = CliApplication.__new__(CliApplication)
        app.client = FakeClient()
        events = []
        inputs = iter(["What is RAG?", "exit"])

        def input_fn(prompt):
            events.append(("input", prompt))
            return next(inputs)

        def output_fn(*args, **kwargs):
            events.append(("output", "".join(str(arg) for arg in args)))

        app.run(input_fn=input_fn, output_fn=output_fn)
        response_index = next(
            i for i, event in enumerate(events)
            if event[0] == "output" and "LLM Response:" in event[1]
        )
        second_input_index = [i for i, event in enumerate(events) if event[0] == "input"][1]
        self.assertIn("answer:What is RAG?", events[response_index][1])
        self.assertLess(response_index, second_input_index)

    def test_cli_rejects_empty_llm_response(self):
        app = CliApplication.__new__(CliApplication)
        app.client = SimpleNamespace(stream=lambda query, model: iter(()))
        with self.assertRaisesRegex(RuntimeError, "empty response"):
            app.run(input_fn=lambda _: "What is RAG?", output_fn=lambda *args, **kwargs: None)


if __name__ == "__main__":
    unittest.main()
