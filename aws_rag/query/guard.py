"""Input and output safety guard for the paper chatbot (/api/chat).

Layer 1 is deterministic and local: it runs inside Lambda, sends nothing anywhere, and
every decision can be explained by the pattern that fired. It blocks prompt-injection
attempts, US Social Security numbers, payment card numbers (Luhn-checked) and leaked
credentials, and redacts emails and phone numbers (arXiv papers routinely print author
emails, so those are masked rather than blocked).

A model-based classifier (Jev, Nemotron Content Safety) can be added as another backend
behind the same Verdict interface; evals/run_guard_eval.py compares backends on the same
labelled cases.

GUARD_MODE: "enforce" (default) blocks and redacts, "monitor" only records the verdict,
"off" disables the guard.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from signup.redaction import PATTERNS as PII_REDACTIONS  # SSN, email, phone (shared with signup)

Direction = Literal["input", "output"]
MODE = os.getenv("GUARD_MODE", "enforce")

INPUT_REFUSAL = ("I can't help with that request. Ask about the papers in the library, and please "
                 "don't include personal identifiers such as Social Security or card numbers.")
OUTPUT_REFUSAL = ("The answer was withheld because it contained sensitive data "
                  "(an identifier or credential). Please rephrase the question.")

# Instructions aimed at the model itself. Questions *about* prompt injection or jailbreaks
# ("how do papers defend against prompt injection?") must pass, so these require the
# imperative form rather than the bare keyword.
INJECTION = [re.compile(p, re.I) for p in (
    r"\b(ignore|disregard|forget|override)\b[^.?!\n]{0,30}\b(previous|prior|above|earlier|all|your|the system)\b[^.?!\n]{0,20}\b(instructions?|prompts?|rules|guidelines|messages?)\b",
    r"\b(reveal|show|print|repeat|output|tell me|what (is|are))\b[^.?!\n]{0,20}\b(your|the)\b[^.?!\n]{0,15}\b(system prompt|hidden (prompt|instructions)|initial instructions|developer (message|prompt))\b",
    r"\byou are (now|no longer)\b[^.?!\n]{0,40}\b(dan|jailbroken|unrestricted|unfiltered|without (any )?(rules|restrictions|limits))\b",
    r"\b(enter|enable|activate|switch to)\b[^.?!\n]{0,15}\b(developer|god|dan|jailbreak) mode\b",
    r"\bpretend\b[^.?!\n]{0,30}\b(no|without) (rules|restrictions|guidelines|filters)\b",
)]
SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SECRETS = {
    "aws_access_key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "api_token": re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|xox[bap]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{35})\b"),
}


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    category: str          # "ok", "redacted", or the reason for a block
    text: str              # the text to use downstream (redacted when allowed)
    backend: str = "patterns"


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _card(text: str) -> bool:
    for match in CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and len(set(digits)) > 1 and _luhn(digits):
            return True
    return False


def check(text: str, direction: Direction) -> Verdict:
    """Deterministic layer-1 verdict for one message or answer."""
    if direction == "input" and any(p.search(text) for p in INJECTION):
        return Verdict(False, "prompt_injection", text)
    if SSN.search(text):
        return Verdict(False, "ssn", text)
    if _card(text):
        return Verdict(False, "payment_card", text)
    for name, pattern in SECRETS.items():
        if pattern.search(text):
            return Verdict(False, f"secret:{name}", text)
    redacted = text
    for pattern, replacement in PII_REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return Verdict(True, "redacted" if redacted != text else "ok", redacted)


def scrub(text: str) -> str:
    """Replace every identifier and credential with a placeholder, without blocking.
    Used for conversation history and anything sent to tracing."""
    if MODE == "off":
        return text
    text = SSN.sub("[SSN]", text)
    text = CARD_CANDIDATE.sub(lambda m: "[CARD]" if _card(m.group()) else m.group(), text)
    for name, pattern in SECRETS.items():
        text = pattern.sub(f"[{name.upper()}]", text)
    for pattern, replacement in PII_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def apply(text: str, direction: Direction) -> tuple[str, Verdict | None]:
    """Text to use and the verdict, honoring GUARD_MODE. Blocked text becomes the refusal."""
    if MODE == "off":
        return text, None
    verdict = check(text, direction)
    if MODE == "monitor":
        return text, verdict
    if not verdict.allowed:
        return (INPUT_REFUSAL if direction == "input" else OUTPUT_REFUSAL), verdict
    return verdict.text, verdict
