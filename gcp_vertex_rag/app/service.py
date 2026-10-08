"""Grounded RAG orchestration independent of HTTP and cloud SDKs."""

from __future__ import annotations

from app.gateways import Generator, Retriever
from app.models import ChatResponse, Citation


NO_EVIDENCE = (
    "I could not find supporting evidence in the indexed coverage-policy documents. "
    "No coverage determination was made."
)


class RagService:
    def __init__(self, retriever: Retriever, generator: Generator) -> None:
        self.retriever = retriever
        self.generator = generator

    def answer(self, raw_question: str) -> ChatResponse:
        question = " ".join(raw_question.replace("\x00", " ").split()).strip()
        if len(question) < 3:
            raise ValueError("Question must contain at least 3 visible characters")
        if len(question) > 2000:
            raise ValueError("Question must not exceed 2000 characters")

        contexts = self.retriever.retrieve(question)
        if not contexts:
            return ChatResponse(answer=NO_EVIDENCE, citations=[], grounded=False)

        evidence = "\n\n".join(
            f"[{index}] Source: {context.source_uri}\n{context.text}"
            for index, context in enumerate(contexts, start=1)
        )
        prompt = f"Question:\n{question}\n\nRetrieved evidence:\n{evidence}"
        answer = self.generator.generate(prompt)
        citations = [
            Citation(id=index, source_uri=context.source_uri, score=context.score)
            for index, context in enumerate(contexts, start=1)
        ]
        return ChatResponse(answer=answer, citations=citations, grounded=True)

