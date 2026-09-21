"""Compare deterministic and LLM interpretation of the same retrieved tables."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

try:  # Support both module and direct-script execution.
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )


DEFAULT_EVAL_PATH = Path(__file__).with_name("table_preference_evals.json")


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def extract_products(rows_json: list[dict[str, Any]], preference: str) -> list[str]:
    """Return products with an exact normalized preference label."""
    target = normalized(preference)
    products: list[str] = []
    for record in rows_json:
        row = {normalized(key): str(value or "").strip() for key, value in record.items()}
        if normalized(row.get("preference", "")) != target:
            continue
        product = row.get("drugname") or row.get("name") or ""
        if product and product not in products:
            products.append(product)
    return products


def exact_product_match(actual: list[str], expected: list[str]) -> bool:
    return {normalized(item) for item in actual} == {
        normalized(item) for item in expected
    }


def parse_product_response(value: str) -> list[str]:
    """Parse the deliberately small JSON contract returned by the LLM."""
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    payload = json.loads(text)
    products = payload.get("products")
    if not isinstance(products, list) or any(
        not isinstance(product, str) for product in products
    ):
        raise ValueError('LLM response must contain a string array named "products"')
    return products


def usage_from_response(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    return {
        "input": int(getattr(usage, "input_tokens", 0) or 0),
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "total": int(getattr(usage, "total_tokens", 0) or 0),
    }


def estimated_cost(
    usage: dict[str, int],
    input_price_per_million: float | None,
    output_price_per_million: float | None,
) -> float | None:
    if input_price_per_million is None or output_price_per_million is None:
        return None
    return (
        usage["input"] * input_price_per_million
        + usage["output"] * output_price_per_million
    ) / 1_000_000


def optional_price(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def langfuse_client() -> Any | None:
    """Return an initialized client only when all credentials are configured."""
    required = (
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip(),
        os.getenv("LANGFUSE_SECRET_KEY", "").strip(),
    )
    if not all(required):
        return None
    from langfuse import get_client

    return get_client()


@dataclass(frozen=True)
class ComparisonSettings:
    database_url: str
    model: str
    top_tables: int = 1
    candidate_rows: int = 20
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None


def _llm_products(
    query: str,
    preference: str,
    table: dict[str, Any],
    settings: ComparisonSettings,
    client: Any,
    langfuse: Any | None,
) -> dict[str, Any]:
    prompt = (
        f"Question: {query}\n"
        f"Target preference label: {preference}\n\n"
        f"Source: {table['source']}\n"
        f"Table: {table['title']}\n"
        f"{table['full_html']}\n\n"
        'Return JSON only in the form {"products": ["product name"]}. '
        "Include every product whose Preference cell exactly matches the target "
        "label after ignoring spaces and hyphens. Do not infer missing products."
    )
    observation = (
        langfuse.start_as_current_observation(
            as_type="generation",
            name="llm-table-interpretation",
            model=settings.model,
            input=prompt,
        )
        if langfuse
        else nullcontext(None)
    )
    started = time.perf_counter()
    with observation as generation:
        response = client.responses.create(
            model=settings.model,
            instructions=(
                "Extract structured facts only from the supplied table. "
                "Never use outside knowledge and return valid JSON only."
            ),
            input=prompt,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        usage = usage_from_response(response)
        cost = estimated_cost(
            usage,
            settings.input_price_per_million,
            settings.output_price_per_million,
        )
        products = parse_product_response(response.output_text)
        if generation:
            update: dict[str, Any] = {
                "output": {"products": products},
                "usage_details": usage,
                "metadata": {"latency_ms": latency_ms},
            }
            if cost is not None:
                update["cost_details"] = {"total": cost}
            generation.update(**update)
    return {
        "products": products,
        "usage": usage,
        "estimated_cost_usd": cost,
        "latency_ms": latency_ms,
    }


def compare_case(
    case: dict[str, Any],
    embedding_model: Any,
    settings: ComparisonSettings,
    *,
    openai_client: Any | None = None,
    langfuse: Any | None = None,
) -> dict[str, Any]:
    """Run both methods against one shared retrieval result."""
    root = (
        langfuse.start_as_current_observation(
            as_type="chain",
            name="table-rag-ab-comparison",
            input={"case_id": case["id"], "query": case["query"]},
            metadata={"dataset": "table-preference", "synthetic_data": True},
        )
        if langfuse
        else nullcontext(None)
    )
    with root as root_observation:
        trace_id = langfuse.get_current_trace_id() if langfuse else None
        retrieval_span = (
            langfuse.start_as_current_observation(
                as_type="retriever",
                name="pgvector-parent-table-retrieval",
                input={
                    "query": case["query"],
                    "top_tables": settings.top_tables,
                    "candidate_rows": settings.candidate_rows,
                },
            )
            if langfuse
            else nullcontext(None)
        )
        retrieval_started = time.perf_counter()
        with retrieval_span as observation:
            with connect(settings.database_url) as connection:
                retrieved = retrieve_tables(
                    connection,
                    embedding_model,
                    case["query"],
                    settings.top_tables,
                    settings.candidate_rows,
                )
            retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
            if observation:
                observation.update(
                    output=[
                        {
                            "source": table["source"],
                            "table_number": table["table_number"],
                            "similarity": float(table["similarity"]),
                        }
                        for table in retrieved
                    ],
                    metadata={"latency_ms": retrieval_ms},
                )

        top = retrieved[0] if retrieved else None
        deterministic_started = time.perf_counter()
        deterministic_products = (
            extract_products(top["rows_json"], case["preference"]) if top else []
        )
        deterministic_ms = (time.perf_counter() - deterministic_started) * 1000
        deterministic_correct = exact_product_match(
            deterministic_products, case["gold_phrases"]
        )
        if langfuse:
            with langfuse.start_as_current_observation(
                as_type="evaluator",
                name="deterministic-table-interpretation",
                input={"preference": case["preference"]},
                output={"products": deterministic_products},
                metadata={
                    "latency_ms": deterministic_ms,
                    "exact_match": deterministic_correct,
                    "llm_tokens": 0,
                    "cost_usd": 0.0,
                },
            ):
                pass

        llm_error = None
        llm_result: dict[str, Any] = {
            "products": [],
            "usage": {"input": 0, "output": 0, "total": 0},
            "estimated_cost_usd": None,
            "latency_ms": 0.0,
        }
        if top:
            try:
                llm_result = _llm_products(
                    case["query"],
                    case["preference"],
                    top,
                    settings,
                    openai_client or OpenAI(),
                    langfuse,
                )
            except (OpenAIError, TypeError, ValueError) as exc:
                llm_error = f"{type(exc).__name__}: {exc}"
        else:
            llm_error = "No table was retrieved"
        llm_correct = llm_error is None and exact_product_match(
            llm_result["products"], case["gold_phrases"]
        )
        result = {
            "case_id": case["id"],
            "query": case["query"],
            "preference": case["preference"],
            "expected_products": case["gold_phrases"],
            "retrieved_source": top["source"] if top else None,
            "retrieved_table_number": top["table_number"] if top else None,
            "expected_table_retrieved": bool(
                top
                and top["source"] == case["source"]
                and top["table_number"] == case["table_number"]
            ),
            "retrieval_latency_ms": retrieval_ms,
            "deterministic": {
                "products": deterministic_products,
                "correct": deterministic_correct,
                "latency_ms": deterministic_ms,
                "tokens": 0,
                "cost_usd": 0.0,
            },
            "llm": {
                "products": llm_result["products"],
                "correct": llm_correct,
                "latency_ms": llm_result["latency_ms"],
                "usage": llm_result["usage"],
                "cost_usd": llm_result["estimated_cost_usd"],
                "error": llm_error,
            },
            "langfuse_trace_id": trace_id,
            "langfuse_trace_url": (
                langfuse.get_trace_url(trace_id=trace_id)
                if langfuse and trace_id
                else None
            ),
        }
        if root_observation:
            root_observation.update(output=result)
    return result


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if not total:
        raise ValueError("At least one comparison result is required")
    deterministic_correct = sum(item["deterministic"]["correct"] for item in results)
    llm_correct = sum(item["llm"]["correct"] for item in results)
    llm_tokens = sum(item["llm"]["usage"]["total"] for item in results)
    known_costs = [
        item["llm"]["cost_usd"]
        for item in results
        if item["llm"]["cost_usd"] is not None
    ]
    return {
        "cases": total,
        "deterministic": {
            "accuracy": deterministic_correct / total,
            "error_rate": 1 - deterministic_correct / total,
            "tokens": 0,
            "cost_usd": 0.0,
        },
        "llm": {
            "accuracy": llm_correct / total,
            "error_rate": 1 - llm_correct / total,
            "tokens": llm_tokens,
            "cost_usd": sum(known_costs) if len(known_costs) == total else None,
            "failed_calls": sum(item["llm"]["error"] is not None for item in results),
        },
    }


def run_comparison(
    cases: list[dict[str, Any]],
    settings: ComparisonSettings,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> dict[str, Any]:
    embedding_model = load_embedding_model(embedding_model_name)
    langfuse = langfuse_client()
    client = OpenAI()
    results = [
        compare_case(
            case,
            embedding_model,
            settings,
            openai_client=client,
            langfuse=langfuse,
        )
        for case in cases
    ]
    if langfuse:
        langfuse.flush()
    return {"summary": summarize(results), "results": results}


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"), override=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    parser.add_argument("--top-tables", type=int, default=1)
    parser.add_argument("--candidate-rows", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    cases = json.loads(args.eval_file.read_text(encoding="utf-8"))[: args.limit]
    settings = ComparisonSettings(
        database_url=args.database_url,
        model=args.model,
        top_tables=args.top_tables,
        candidate_rows=args.candidate_rows,
        input_price_per_million=optional_price("OPENAI_INPUT_COST_PER_1M_USD"),
        output_price_per_million=optional_price("OPENAI_OUTPUT_COST_PER_1M_USD"),
    )
    print(json.dumps(run_comparison(cases, settings, args.embedding_model), indent=2))


if __name__ == "__main__":
    main()
