"""Private Cloud Run API and demonstration UI."""

from __future__ import annotations

import logging
import re
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.gateways import VertexGeminiGenerator, VertexRagRetriever
from app.models import ChatRequest, ChatResponse
from app.service import RagService

LOGGER = logging.getLogger("gcp_vertex_rag")
STATIC_DIR = Path(__file__).parent / "static"
REQUEST_ID_PATTERN = re.compile(r"[^A-Za-z0-9._:-]")


@lru_cache(maxsize=1)
def get_service() -> RagService:
    settings = Settings.from_env()
    return RagService(VertexRagRetriever(settings), VertexGeminiGenerator(settings))


def create_app(service: RagService | None = None) -> FastAPI:
    application = FastAPI(title="GEHA Vertex AI RAG sample", version="0.1.0")

    if service is not None:
        application.dependency_overrides[get_service] = lambda: service

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        supplied_id = request.headers.get("x-request-id", "")[:128]
        request_id = REQUEST_ID_PATTERN.sub("", supplied_id) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @application.post("/api/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        request: Request,
        rag_service: RagService = Depends(get_service),
    ) -> ChatResponse:
        try:
            response = rag_service.answer(payload.question)
            LOGGER.info(
                "chat_complete request_id=%s grounded=%s citations=%d",
                request.state.request_id,
                response.grounded,
                len(response.citations),
            )
            return response
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            # Deliberately do not log question text or retrieved evidence.
            LOGGER.error(
                "chat_failed request_id=%s error_type=%s",
                request.state.request_id,
                type(exc).__name__,
            )
            raise HTTPException(status_code=502, detail="The RAG service is temporarily unavailable") from exc

    return application


app = create_app()
