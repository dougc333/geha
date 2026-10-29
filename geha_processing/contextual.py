"""Shared Anthropic contextual-retrieval prompt and client contract."""

from __future__ import annotations

from typing import Any, Callable, TypedDict


CLAUDE_MODEL = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PROMPT_VERSION = "anthropic-contextual-retrieval-v1"
SYSTEM_PROMPT = (
    "You prepare concise context for retrieval indexing. Use only the supplied "
    "document. Do not answer questions, add advice, or introduce facts absent "
    "from the document."
)
USER_TEMPLATE = """Here is the chunk we want to situate within the whole document.
<chunk>
{chunk}
</chunk>
Please give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk. Include
the document subject and any policy code, entity, section, or time period needed
to disambiguate it. Answer only with the succinct context and nothing else."""


class ClaudeContextResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


ContextGenerator = Callable[[str, str], str | ClaudeContextResult]


def contextual_retrieval_prompt(document: str, chunk: str) -> dict[str, Any]:
    return {
        "system": [
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": f"<document>\n{document}\n</document>",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "message": USER_TEMPLATE.format(chunk=chunk),
    }


def make_claude_context_generator(
    model: str = CLAUDE_MODEL,
    *,
    fallback_beta: str = FALLBACK_BETA,
    refusal_error: type[Exception] = RuntimeError,
) -> ContextGenerator:
    import anthropic

    client = anthropic.Anthropic(max_retries=2, timeout=180)

    def generate(document: str, chunk: str) -> ClaudeContextResult:
        prompt = contextual_retrieval_prompt(document, chunk)
        with client.beta.messages.stream(
            model=model,
            max_tokens=256,
            system=prompt["system"],
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt["message"]}],
            }],
            betas=[fallback_beta],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            category = (
                getattr(message.stop_details, "category", None)
                if message.stop_details else None
            )
            raise refusal_error(
                f"Claude declined contextualization (category: {category})"
            )
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        return {
            "context": " ".join(text.split()).strip(),
            "input_tokens": int(usage.input_tokens),
            "output_tokens": int(usage.output_tokens),
            "cache_creation_input_tokens": int(usage.cache_creation_input_tokens or 0),
            "cache_read_input_tokens": int(usage.cache_read_input_tokens or 0),
        }

    return generate
