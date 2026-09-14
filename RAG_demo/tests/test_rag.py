import httpx
import pytest
from rag import load_chunks, build_graph


def test_tables_preserve_distinct_rows():
    chunks = load_chunks()
    table = next(
        c
        for c in chunks
        if c["metadata"]["document_id"] == "bendamustine"
        and c["metadata"]["page"] == 1
        and c["metadata"]["kind"] == "table"
    )
    assert "| Preferred | Yes | Treanda | J9033 |" in table["text"]
    assert (
        "| Preferred | Yes | Bendamustine 505(b)(2) Dr Reddy’s | J9999 |"
        in table["text"]
    )
    assert len(table["text"].splitlines()) == 7
    assert not any("remaining deductible balance" in c["text"] for c in chunks)


def test_table_boundary_does_not_garble_prose():
    text = " ".join(
        c["text"]
        for c in load_chunks()
        if c["metadata"]["document_id"] == "bendamustine"
    )
    assert (
        "Members must have documentation of a contraindication, failure, or intolerance"
        in text
    )


class FakeRetriever:
    def search(self, *args, **kwargs):
        return [
            {
                "id": "source-1",
                "text": "Policy content",
                "metadata": {"source_file": "policy.pdf", "page": 1},
            }
        ]


def test_search_only_never_calls_model(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: pytest.fail("Unexpected model call")
    )
    result = build_graph(FakeRetriever()).invoke({"question": "hi"})
    assert result["mode"] == "retrieval_only"


def test_unknown_citation_rejected(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"answer":"yes","citation_ids":["invented"],"abstained":false}'
                        }
                    }
                ]
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="citations"):
        build_graph(FakeRetriever(), "http://localhost", "fake", generate=True).invoke(
            {"question": "hi"}
        )


def test_generated_answer_retains_source_page(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"answer":"Supported answer","citation_ids":["source-1"],"abstained":false}'
                        }
                    }
                ]
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    result = build_graph(
        FakeRetriever(), "http://localhost", "fake", generate=True
    ).invoke({"question": "hi"})
    assert result["answer"] == "Supported answer"
    assert result["citations"][0]["metadata"]["page"] == 1
