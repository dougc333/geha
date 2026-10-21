"""Class-based CLI application corresponding to the original app.py."""

from __future__ import annotations
from typing import Any, Callable
from jsonargparse import CLI
from rag_client_class import RagClient
from rag_class import Rag


class CliApplication:
    """Interactive command-line wrapper around :class:`RagClient`."""

    def __init__(
        self,
        file: str = "../data/2306.02707.pdf",
        *,
        client: Any | None = None,
        client_factory: Callable[..., Any] = RagClient,
        rag_service: Rag | None = None,
    ) -> None:
        self.file = file
        self.rag = rag_service or Rag()
        self.client = client or client_factory(
            file,
            multi_query=True,
            rag_service=self.rag,
        )

    def answer(self, query: str, reranker_model: str = "gpt") -> str:
        contexts = self.client.retrieve_context_reranked(query, reranker_model)
        context = self.client.format_context(contexts)
        return self.client.chain.invoke({"context": context, "question": query})

    def stream_answer(self, query: str, reranker_model: str = "gpt"):
        yield from self.client.stream(query, reranker_model)

    def run(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[..., Any] = print,
    ) -> None:
        while True:
            query = input_fn("User Input: ")
            if query == "exit":
                return
            # Consume the stream completely before displaying the response.
            # This prevents an empty "LLM Response" prompt from appearing while
            # retrieval/generation is still running, and guarantees the next
            # input prompt is not requested until a response is available.
            response = "".join(str(chunk) for chunk in self.stream_answer(query))
            if not response.strip():
                raise RuntimeError("The LLM returned an empty response")
            output_fn(f"\n\nLLM Response: {response}\n", flush=True)


def main(file: str = "../data/2306.02707.pdf") -> None:
    CliApplication(file=file).run()


if __name__ == "__main__":
    CLI(main)
