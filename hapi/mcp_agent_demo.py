#!/usr/bin/env python3
"""Demo: Claude answers a question about the synthetic patients through the MCP server.

Starts bin/langcare-mcp-fhir (stdio) against the local HAPI server, gives Claude its
read-only tools (fhir_search, fhir_read; create/update are not offered), and runs a
tool-use loop, printing every FHIR call. Synthetic Synthea data only.

    ANTHROPIC_API_KEY=... python mcp_agent_demo.py ["your question"]
"""

from __future__ import annotations

import json
import select
import subprocess
import sys
import time
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5-5"
READ_ONLY_TOOLS = {"fhir_search", "fhir_read"}
QUESTION = ("Which patients have type 2 diabetes? For each one, give their name, age, most "
            "recent HbA1c with its date, and how many insurance claims (ExplanationOfBenefit) "
            "they have and the total amount paid across them.")
SYSTEM = ("You answer questions about a FHIR R4 server that contains synthetic (Synthea) test "
          "patients, using the fhir_search and fhir_read tools. Use standard codes (SNOMED "
          "44054006 for type 2 diabetes, LOINC 4548-4 for HbA1c). Keep searches small with "
          "_count and _elements where you can. Report numbers exactly as the data gives them "
          "and say when something isn't in the data.")


class McpStdio:
    """Minimal MCP client over stdio (JSON-RPC, one message per line)."""

    def __init__(self, command: list[str]):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.next_id = 0

    def request(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _, _ = select.select([self.proc.stdout], [], [], 1)
            if ready:
                line = self.proc.stdout.readline()
                if not line:
                    break
                message = json.loads(line)
                if message.get("id") == self.next_id:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message["result"]
        raise TimeoutError(f"no MCP response to {method}")

    def _send(self, message: dict) -> None:
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def start(self) -> list[dict]:
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "mcp_agent_demo", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self.request("tools/list")["tools"]

    def call(self, name: str, arguments: dict) -> tuple[str, bool]:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        return text, bool(result.get("isError"))

    def close(self) -> None:
        self.proc.terminate()


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    mcp = McpStdio([str(HERE / "bin" / "langcare-mcp-fhir"), "-config", str(HERE / "langcare-config.yaml")])
    tools = [{"name": t["name"], "description": t.get("description", ""), "input_schema": t["inputSchema"]}
             for t in mcp.start() if t["name"] in READ_ONLY_TOOLS]
    print(f"MCP tools offered to Claude: {[t['name'] for t in tools]}\n\nQ: {question}\n")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    calls = 0
    try:
        while True:
            response = client.beta.messages.create(
                model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools, messages=messages,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            if response.stop_reason == "refusal":
                sys.exit(f"Refused: {response.stop_details}")
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                calls += 1
                print(f"  [{calls}] {block.name} {json.dumps(block.input)}")
                text, is_error = mcp.call(block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": text[:60000], "is_error": is_error})
            messages.append({"role": "user", "content": results})
    finally:
        mcp.close()
    print("\nA:", "".join(b.text for b in response.content if b.type == "text"))
    print(f"\n({calls} FHIR calls through MCP; model {response.model})")


if __name__ == "__main__":
    main()
