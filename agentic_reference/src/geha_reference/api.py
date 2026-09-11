from __future__ import annotations

from dataclasses import asdict

from .bootstrap import build_agent
from .models import UserContext


def create_app():
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel, Field
    except ImportError as error:
        raise RuntimeError("Install the 'api' extra to run the HTTP API") from error

    agent = build_agent()
    app = FastAPI(title="GEHA Agentic Reference", version="0.1.0")

    class QueryRequest(BaseModel):
        message: str = Field(min_length=1, max_length=4000)
        actor_id: str
        role: str
        subject_member_ids: list[str] = Field(default_factory=list)
        authorized_claim_ids: list[str] = Field(default_factory=list)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/v1/query")
    def query(request: QueryRequest):
        # Demo only: production must derive these attributes from verified JWT
        # or session claims, not accept them from a caller-controlled body.
        context = UserContext(
            actor_id=request.actor_id,
            role=request.role,
            subject_member_ids=frozenset(request.subject_member_ids),
            authorized_claim_ids=frozenset(request.authorized_claim_ids),
        )
        return asdict(agent.run(request.message, context))

    return app
