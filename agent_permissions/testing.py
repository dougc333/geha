"""Test helpers: a scripted chat model that create_agent accepts (no LLM calls)."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Plays back AIMessages in order and records the messages it was shown."""

    replies: list[AIMessage] = Field(default_factory=list)
    seen: list[list] = Field(default_factory=list)
    bound_tools: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = [getattr(t, "name", None) or t.get("name") for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])
