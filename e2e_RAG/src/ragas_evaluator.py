"""Ragas evaluation adapter for the e2e RAG application.

Evaluation is deliberately separate from the online answer path.  Running it
uses evaluator-model and embedding API calls; ordinary CLI and Streamlit chat
do not import Ragas or incur those calls.
"""

from __future__ import annotations

import json
import sys
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class RagasSample:
    """One completed RAG interaction plus its approved reference answer."""

    user_input: str
    response: str
    retrieved_contexts: list[str]
    reference: str
    reference_contexts: list[str] | None = None

    def __post_init__(self) -> None:
        if not self.user_input.strip():
            raise ValueError("user_input must not be empty")
        if not self.response.strip():
            raise ValueError("response must not be empty")
        if not self.retrieved_contexts:
            raise ValueError("retrieved_contexts must contain at least one passage")
        if not self.reference.strip():
            raise ValueError("reference must not be empty")


MetricRunner = Callable[[RagasSample], dict[str, Any]]


def _install_vertexai_import_compatibility() -> None:
    """Work around Ragas importing a removed optional LangChain module.

    Ragas 0.4.3 imports ChatVertexAI unconditionally even when evaluation uses
    OpenAI. Modern langchain-community removed that module. A placeholder is
    sufficient because this evaluator never constructs or calls Vertex AI.
    """
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        __import__(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        compatibility_module = types.ModuleType(module_name)

        class ChatVertexAI:  # pragma: no cover - only used by Ragas isinstance checks
            pass

        compatibility_module.ChatVertexAI = ChatVertexAI
        sys.modules[module_name] = compatibility_module


class RagasEvaluator:
    """Score completed RAG interactions with the Ragas collections API."""

    def __init__(
        self,
        *,
        evaluator_model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
        metric_runner: MetricRunner | None = None,
    ) -> None:
        self.evaluator_model = evaluator_model
        self.embedding_model = embedding_model
        self.metric_runner = metric_runner

    def _default_metric_runner(self) -> MetricRunner:
        _install_vertexai_import_compatibility()
        try:
            from openai import OpenAI
            from ragas.embeddings.base import embedding_factory
            from ragas.llms import llm_factory
            from ragas.metrics.collections import (
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )
        except ImportError as error:
            raise RuntimeError(
                "Ragas is not installed. Install e2e_RAG/requirements.txt first."
            ) from error

        client = OpenAI()
        evaluator_llm = llm_factory(self.evaluator_model, client=client)
        evaluator_embeddings = embedding_factory(
            "openai",
            model=self.embedding_model,
            client=client,
            interface="modern",
        )
        metrics: list[tuple[str, Any, tuple[str, ...]]] = [
            (
                "faithfulness",
                Faithfulness(llm=evaluator_llm),
                ("user_input", "response", "retrieved_contexts"),
            ),
            (
                "answer_relevancy",
                AnswerRelevancy(
                    llm=evaluator_llm,
                    embeddings=evaluator_embeddings,
                ),
                ("user_input", "response"),
            ),
            (
                "context_precision",
                ContextPrecision(llm=evaluator_llm),
                ("user_input", "reference", "retrieved_contexts"),
            ),
            (
                "context_recall",
                ContextRecall(llm=evaluator_llm),
                ("user_input", "reference", "retrieved_contexts"),
            ),
        ]

        def run(sample: RagasSample) -> dict[str, Any]:
            values = asdict(sample)
            scores: dict[str, Any] = {}
            for name, metric, required_fields in metrics:
                result = metric.score(
                    **{field: values[field] for field in required_fields}
                )
                scores[name] = {
                    "value": float(result.value),
                    "reason": getattr(result, "reason", None),
                }
            return scores

        return run

    def evaluate(self, samples: Iterable[RagasSample]) -> dict[str, Any]:
        sample_list = list(samples)
        if not sample_list:
            raise ValueError("At least one evaluation sample is required")
        runner = self.metric_runner or self._default_metric_runner()
        rows = [
            {**asdict(sample), "scores": runner(sample)}
            for sample in sample_list
        ]
        metric_names = sorted({name for row in rows for name in row["scores"]})
        aggregate = {
            name: mean(
                float(row["scores"][name]["value"])
                for row in rows
                if name in row["scores"]
            )
            for name in metric_names
        }
        return {
            "evaluator_model": self.evaluator_model,
            "embedding_model": self.embedding_model,
            "sample_count": len(rows),
            "aggregate": aggregate,
            "samples": rows,
        }

    @staticmethod
    def write_json(path: Path, result: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
