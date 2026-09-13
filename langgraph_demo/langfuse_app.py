"""Run the synthetic GEHA LangGraph workflow with local Langfuse tracing."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.langchain import CallbackHandler

from demo import ROOT, load_inputs, resume, workflow


load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class LangfuseSettings:
    base_url: str
    public_key: str
    secret_key: str


def settings_from_env() -> LangfuseSettings:
    """Load and validate credentials for the local Langfuse project."""
    values = {
        "LANGFUSE_BASE_URL": os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000").strip(),
        "LANGFUSE_PUBLIC_KEY": os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip(),
        "LANGFUSE_SECRET_KEY": os.environ.get("LANGFUSE_SECRET_KEY", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing Langfuse configuration: " + ", ".join(missing)
            + ". Copy .env.example to .env and add the keys from the Langfuse project settings."
        )
    if not values["LANGFUSE_PUBLIC_KEY"].startswith("pk-lf-"):
        raise RuntimeError("LANGFUSE_PUBLIC_KEY must contain the pk-lf-... value, not its variable name.")
    if not values["LANGFUSE_SECRET_KEY"].startswith("sk-lf-"):
        raise RuntimeError("LANGFUSE_SECRET_KEY must contain the sk-lf-... value, not its variable name.")
    return LangfuseSettings(
        base_url=values["LANGFUSE_BASE_URL"].rstrip("/"),
        public_key=values["LANGFUSE_PUBLIC_KEY"],
        secret_key=values["LANGFUSE_SECRET_KEY"],
    )


def trace_id_for_thread(thread_id: str) -> str:
    """Use one stable Langfuse trace for the start and human-review resume."""
    return Langfuse.create_trace_id(seed=f"geha-langgraph-demo:{thread_id}")


def graph_config(thread_id: str, handler: CallbackHandler, operation: str) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": [handler],
        "run_name": f"geha-{operation}",
        "tags": ["geha", "synthetic", "langgraph", operation],
        "metadata": {
            "application": "geha-langgraph-demo",
            "operation": operation,
            "synthetic_data": True,
        },
    }


def checked_client(settings: LangfuseSettings):
    client = get_client()
    if not client.auth_check():
        raise RuntimeError(
            f"Langfuse authentication failed at {settings.base_url}. "
            "Check that Docker is running and the project keys match this local instance."
        )
    return client


def traced_start(graph, claim_id: str, actor: str, thread_id: str, client) -> dict[str, Any]:
    payload = {"claim_id": claim_id, "actor": actor}
    handler = CallbackHandler()
    trace_id = trace_id_for_thread(thread_id)
    config = graph_config(thread_id, handler, "start")
    with client.start_as_current_observation(
        trace_context={"trace_id": trace_id},
        name="geha-claim-review",
        as_type="agent",
        input=payload,
        metadata={"synthetic_data": True},
    ) as observation:
        with propagate_attributes(
            trace_name="GEHA synthetic claim review",
            user_id=actor,
            session_id=thread_id,
            tags=["geha", "synthetic", "langgraph"],
            metadata={"claim_id": claim_id, "workflow": "human-review"},
        ):
            graph.invoke(payload, config)
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        output = {"thread_id": thread_id, "next": snapshot.next, "state": snapshot.values}
        observation.update(output=output)
    client.flush()
    return {**output, "langfuse_trace_id": trace_id}


def traced_review(
    graph,
    thread_id: str,
    action: str,
    reason: str,
    edited_text: str | None,
    client,
) -> dict[str, Any]:
    handler = CallbackHandler()
    trace_id = trace_id_for_thread(thread_id)
    input_data = {"thread_id": thread_id, "action": action, "reason": reason}
    with client.start_as_current_observation(
        trace_context={"trace_id": trace_id},
        name="human-review-resume",
        as_type="span",
        input=input_data,
        metadata={"synthetic_data": True},
    ) as observation:
        with propagate_attributes(
            trace_name="GEHA synthetic claim review",
            user_id="reviewer",
            session_id=thread_id,
            tags=["geha", "synthetic", "langgraph", "human-review"],
            metadata={"review_action": action},
        ):
            resume(
                graph,
                thread_id,
                action,
                reason,
                edited_text=edited_text,
                callbacks=[handler],
                run_name="geha-review-resume",
                tags=["geha", "synthetic", "review"],
                metadata={"synthetic_data": True, "operation": "review"},
            )
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        output = {"thread_id": thread_id, "next": snapshot.next, "state": snapshot.values}
        observation.update(output=output)
    client.flush()
    return {**output, "langfuse_trace_id": trace_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT.parent)
    parser.add_argument("--db", type=Path, default=ROOT / "data/checkpoints.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Verify authentication with local Langfuse")
    start = commands.add_parser("start", help="Start and trace a synthetic claim review")
    start.add_argument("--claim")
    start.add_argument(
        "--actor",
        choices=["member", "outsider", "demo_operator"],
        default="member",
    )
    review = commands.add_parser("review", help="Resume and trace the human-review step")
    review.add_argument("thread")
    review.add_argument("--action", choices=["approve", "reject"], required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--edit")
    args = parser.parse_args()

    settings = settings_from_env()
    client = checked_client(settings)
    if args.command == "check":
        print(json.dumps({"authenticated": True, "base_url": settings.base_url}, indent=2))
        client.flush()
        return

    with workflow(args.db, args.base) as graph:
        if args.command == "start":
            claim_id = args.claim or load_inputs(args.base)[3]
            result = traced_start(graph, claim_id, args.actor, str(uuid.uuid4()), client)
        else:
            result = traced_review(graph, args.thread, args.action, args.reason, args.edit, client)
    print(json.dumps(result, indent=2))
    print(f"Langfuse: {settings.base_url} (trace {result['langfuse_trace_id']})")


if __name__ == "__main__":
    main()
