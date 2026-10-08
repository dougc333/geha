"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_id: str
    location: str
    corpus_name: str
    model_name: str = "gemini-2.5-flash"
    top_k: int = 6

    @classmethod
    def from_env(cls) -> "Settings":
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
        corpus_name = os.getenv("VERTEX_RAG_CORPUS", "").strip()
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        try:
            top_k = int(os.getenv("RAG_TOP_K", "6"))
        except ValueError as exc:
            raise ValueError("RAG_TOP_K must be an integer") from exc

        missing = [
            name
            for name, value in {
                "GOOGLE_CLOUD_PROJECT": project_id,
                "VERTEX_RAG_CORPUS": corpus_name,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        if not 1 <= top_k <= 20:
            raise ValueError("RAG_TOP_K must be between 1 and 20")
        return cls(project_id, location, corpus_name, model_name, top_k)

