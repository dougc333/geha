"""PII-safe Langfuse helpers for one trace per signup turn."""

from __future__ import annotations

import hashlib
import hmac
import os
from contextlib import contextmanager

from langfuse import propagate_attributes

from app import langfuse
from .redaction import sanitize


def pseudonymous_user_id(member_ref: str) -> str | None:
    key = os.getenv("SIGNUP_HASH_KEY", "")
    if not key:
        return None
    return hmac.new(key.encode(), member_ref.encode(), hashlib.sha256).hexdigest()


@contextmanager
def signup_turn(application: dict, message: str):
    attributes = {
        "session_id": str(application["id"]),
        "tags": ["signup", application["product"], str(application["coverage_year"])],
    }
    user_id = pseudonymous_user_id(application["member_ref"])
    if user_id:
        attributes["user_id"] = user_id
    with propagate_attributes(**attributes):
        with langfuse.start_as_current_observation(
            as_type="agent",
            name="signup-turn",
            input=sanitize({
                "message_length": len(message),
                "stage": application["stage"],
                "version": application["version"],
            }),
        ) as observation:
            yield observation
