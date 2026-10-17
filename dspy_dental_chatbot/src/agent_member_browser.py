"""Simulated members using the real Streamlit page, in a visible Chrome window.

Same personas and member model as agent_member.py, but every turn goes through
the browser: the script reads the bot's last chat message from the page, asks
the simulated member (Amazon Nova Lite on Bedrock) for a reply, types it into
the chat box and waits for the bot to answer. Each persona gets a fresh browser
context, so a fresh chat session.

Start the app first (streamlit run src/app.py --server.port 8506), then:

    python src/agent_member_browser.py --url http://localhost:8506
    python src/agent_member_browser.py --persona widow --headless
"""

from __future__ import annotations

import argparse
import sys

import boto3
from playwright.sync_api import sync_playwright

from agent_member import MAX_TURNS, PERSONAS, member_reply

# What the chat must show for each persona. Checked against the page text, since the
# browser can't see the graph state that agent_member.py checks.
EXPECT_TEXT = {
    "routine-retiree": ["Recommended plan: Standard", "Enrollment estimate complete"],
    "widow": ["QLE policy table for Losing a covered family member"],
    "new-baby": ["QLE policy table for Acquiring an eligible family member"],
    "braces-new-hire": ["Recommended plan: High", "Enrollment estimate complete: High, Self Plus One"],
}
MESSAGE = '[data-testid="stChatMessage"]'
INPUT = '[data-testid="stChatInputTextArea"]'
DONE = ("Enrollment estimate complete", "This QLE session is complete", "cannot confirm eligibility")
FINAL_RESPONSE_PAUSE_MS = 5000


def chat(page) -> list[tuple[str, str]]:
    """The conversation as shown on the page: ("bot" | "member", text) per message."""
    out = []
    for m in page.locator(MESSAGE).all():
        who = "bot" if m.locator('[data-testid="stChatMessageAvatarAssistant"]').count() else "member"
        out.append((who, m.locator('[data-testid="stChatMessageContent"]').inner_text().strip()))
    return out


def run(name: str, persona: dict, client, browser, url: str, pause_ms: int, type_delay_ms: int) -> dict:
    context = browser.new_context(viewport={"width": 900, "height": 900})
    page = context.new_page()
    page.goto(url)
    page.wait_for_selector(MESSAGE)
    print(f"\n=== {name} ===\nfacts: {persona['facts']}\nstyle: {persona['style']}")
    for turn in range(1, MAX_TURNS + 1):
        transcript = chat(page)
        print(f"BOT: {transcript[-1][1]}")
        if page.locator(INPUT).is_disabled() or any(d in transcript[-1][1] for d in DONE):
            break
        said = member_reply(client, persona, transcript)
        print(f"--- turn {turn}: {name} types ---\nMEMBER: {said}")
        page.locator(INPUT).click()
        page.locator(INPUT).press_sequentially(said, delay=type_delay_ms)  # visible typing
        page.wait_for_timeout(1000)  # leave the typed text on screen before sending
        page.keyboard.press("Enter")
        # Wait for the member's message and the bot's answer to both appear.
        page.wait_for_function(
            """([sel, n]) => {
                const m = document.querySelectorAll(sel);
                return m.length >= n && m[m.length - 1].querySelector('[data-testid="stChatMessageAvatarAssistant"]');
            }""",
            arg=[MESSAGE, len(transcript) + 2], timeout=30000)
        page.wait_for_timeout(pause_ms)
    text = "\n".join(t for _, t in chat(page))
    missing = [e for e in EXPECT_TEXT[name] if e not in text]
    # Keep the completed conversation visible long enough to inspect the result.
    page.wait_for_timeout(FINAL_RESPONSE_PAUSE_MS)
    context.close()
    return {"persona": name, "passed": not missing,
            "clarifications": text.count("could mean more than one"), "missing": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8506")
    parser.add_argument("--persona", default="all", choices=["all", *PERSONAS])
    parser.add_argument("--headless", action="store_true", help="don't show the Chrome window")
    parser.add_argument("--pause-ms", type=int, default=3000, help="pause after each bot answer, to watch")
    parser.add_argument("--type-delay-ms", type=int, default=35, help="delay between typed characters")
    args = parser.parse_args()
    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    names = list(PERSONAS) if args.persona == "all" else [args.persona]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=args.headless, slow_mo=60)
        results = [run(n, PERSONAS[n], client, browser, args.url, args.pause_ms, args.type_delay_ms) for n in names]
        browser.close()
    print("\npersona            result  clarify  missing text")
    for r in results:
        print(f"{r['persona']:<18} {'PASS' if r['passed'] else 'FAIL':<7} {r['clarifications']:>7}  {r['missing'] or ''}")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
