"""FastAPI endpoints for resumable guided dental signup."""

from __future__ import annotations

import os
import time
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request

from app import GENERATION_MODEL, RERANK_CANDIDATES, _rerank, converse, database, langfuse
from retrieval import hybrid_retrieve

from . import repository
from .graph import prompt_for
from .models import CreateSignupRequest, SignupMessageRequest
from .redaction import sanitize
from .service import initial_reply, process_turn
from .tracing import signup_turn


router = APIRouter(prefix="/api/signup", tags=["signup"])
DEFAULT_DOCUMENT_IDS = [
    item.strip() for item in os.getenv("SIGNUP_DOCUMENT_IDS", "").split(",") if item.strip()
]
AUTH_REQUIRED = os.getenv("SIGNUP_AUTH_REQUIRED", "false").lower() in {"1", "true", "yes"}


def _principal(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    subject = claims.get("sub")
    if subject:
        return str(subject)
    if AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail="Authenticated member identity is required")
    return "local-demo-member"


def _text(response: dict) -> str:
    return "".join(
        block["text"] for block in response["output"]["message"]["content"] if "text" in block
    ).strip()


def _benefit_answer(question: str, document_ids: list[str]) -> tuple[str, list[dict]]:
    timings: dict[str, float] = {}
    with database() as connection:
        candidates = hybrid_retrieve(
            connection, question, document_ids, timings, trace_query=False
        )
    sources = _rerank(
        question, candidates[:RERANK_CANDIDATES], trace_query=False
    )[:6]
    if not sources:
        return "I couldn't find that answer in the mapped benefits brochure.", []
    context = "\n\n".join(
        f"[{number}] {row['title']}, page {row['page']}\n{row['content']}"
        for number, row in enumerate(sources, start=1)
    )
    answer = _text(converse(
        "signup-benefit-answer",
        trace_input=False,
        trace_output=False,
        modelId=GENERATION_MODEL,
        system=[{"text": (
            "Answer only from the supplied dental plan sources. Cite claims inline as [1] or [2]. "
            "Do not determine eligibility, quote an unprovided premium, or claim enrollment is complete."
        )}],
        messages=[{"role": "user", "content": [{"text":
            f"SOURCES:\n{context}\n\nMEMBER QUESTION:\n{question}"}]}],
        inferenceConfig={"maxTokens": 700, "temperature": 0.1},
    ))
    return answer, [
        {
            "n": number,
            "title": row["title"],
            "document_id": row["document_id"],
            "page": row["page"],
            "chunk_id": row["id"],
            "rerank_score": row.get("rerank_score"),
            "snippet": row["content"][:400],
        }
        for number, row in enumerate(sources, start=1)
    ]


def _load(application_id: UUID, member_ref: str) -> dict:
    try:
        with database() as connection:
            return repository.get_application(connection, str(application_id), member_ref)
    except repository.ApplicationNotFound as exc:
        raise HTTPException(status_code=404, detail="Signup application not found") from exc


@router.post("/sessions", status_code=201)
def create_session(payload: CreateSignupRequest, request: Request) -> dict:
    member_ref = _principal(request)
    with database() as connection:
        application = repository.create_application(
            connection, str(uuid4()), member_ref, payload.product, payload.coverage_year
        )
    return initial_reply(application)


@router.get("/{application_id}")
def get_session(application_id: UUID, request: Request) -> dict:
    application = _load(application_id, _principal(request))
    return {
        "application": application,
        "reply": prompt_for(application["stage"], application["slots"]),
    }


@router.post("/{application_id}/messages")
def message(application_id: UUID, payload: SignupMessageRequest, request: Request) -> dict:
    member_ref = _principal(request)
    application = _load(application_id, member_ref)
    if payload.expected_version != application["version"]:
        raise HTTPException(
            status_code=409,
            detail="Signup was updated by another request; reload it and retry",
        )
    with database() as connection:
        replay = repository.get_idempotent_response(
            connection, str(application_id), str(payload.client_message_id)
        )
        if replay:
            return {**replay, "idempotent_replay": True}
        document_ids = repository.document_ids_for_plan(
            connection,
            application["product"],
            application["coverage_year"],
            application["slots"].get("selected_plan"),
        )
    document_ids = document_ids or DEFAULT_DOCUMENT_IDS

    started = time.perf_counter()
    with signup_turn(application, payload.message) as observation:
        response = process_turn(
            application,
            payload.message,
            payload.slot_updates,
            document_ids,
            _benefit_answer,
        )
        try:
            with database() as connection:
                response = repository.save_turn(
                    connection,
                    response["application"],
                    payload.expected_version,
                    str(payload.client_message_id),
                    payload.message,
                    response,
                    response["event"],
                )
        except repository.VersionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail="Signup was updated by another request; reload it and retry",
            ) from exc
        observation.update(
            output=sanitize({
                "event": response["event"],
                "stage": response["application"]["stage"],
                "status": response["application"]["status"],
                "source_count": len(response["sources"]),
            }),
            metadata={"duration_ms": round((time.perf_counter() - started) * 1000, 1)},
        )
        response["trace_id"] = langfuse.get_current_trace_id()
        response["idempotent_replay"] = False
        return response


@router.post("/{application_id}/confirm")
def confirm(application_id: UUID, payload: SignupMessageRequest, request: Request) -> dict:
    confirmed = payload.model_copy(update={"message": "confirm"})
    return message(application_id, confirmed, request)


@router.post("/{application_id}/handoff")
def handoff(application_id: UUID, payload: SignupMessageRequest, request: Request) -> dict:
    member_ref = _principal(request)
    application = _load(application_id, member_ref)
    if payload.expected_version != application["version"]:
        raise HTTPException(status_code=409, detail="Signup was updated; reload and retry")
    response = {
        "application": {**application, "stage": "handoff", "status": "handoff"},
        "reply": "I’ll connect you with a benefits specialist to continue.",
        "event": "handoff",
        "sources": [],
    }
    try:
        with database() as connection:
            response = repository.save_turn(
                connection,
                response["application"],
                payload.expected_version,
                str(payload.client_message_id),
                payload.message,
                response,
                "handoff",
            )
    except repository.VersionConflict as exc:
        raise HTTPException(status_code=409, detail="Signup was updated; reload and retry") from exc
    return {**response, "trace_id": None, "idempotent_replay": False}
