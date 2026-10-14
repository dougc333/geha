"""Tests for the policy engine, script inspection and PermissionMiddleware. No LLM calls.

    cd /Users/dc/geha
    uv run --no-project --python 3.12 --with 'langchain==1.4.2' --with pyyaml \
        python -m unittest discover -s agent_permissions -p 'test_*.py' -v
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_permissions import (ALLOW, ASK, DENY, MemoryAuditLog, PermissionMiddleware, Policy, Rule,
                               inspect_call, inspect_command, load_policy, policy_from_dict)
from agent_permissions.policies import benefits_policy, fhir_agent_policy, fraud_policy, pharmacy_policy
from agent_permissions.testing import ScriptedChatModel, call

RAN: list[str] = []
logging.getLogger("agent_permissions").setLevel(logging.CRITICAL)  # fail-closed paths log tracebacks


@tool
def fhir_read(resource_type: str, id: str) -> str:
    """Read one FHIR resource."""
    RAN.append("fhir_read")
    return f"{resource_type}/{id}"


@tool
def fhir_delete(resource_type: str, id: str) -> str:
    """Delete one FHIR resource."""
    RAN.append("fhir_delete")
    return "deleted"


@tool
def shell(command: str) -> str:
    """Run a shell command."""
    RAN.append("shell")
    return "ran"


def tool_messages(state) -> list[ToolMessage]:
    return [m for m in state["messages"] if isinstance(m, ToolMessage)]


class PolicyTests(unittest.TestCase):
    def test_first_matching_rule_wins_and_default_applies(self):
        policy = Policy([Rule("fhir_read", ALLOW, "read"), Rule("fhir_*", DENY, "other fhir")], default=ASK)
        self.assertEqual(policy.evaluate("fhir_read", {}).decision, ALLOW)
        self.assertEqual(policy.evaluate("fhir_delete", {}).decision, DENY)
        verdict = policy.evaluate("mystery", {})
        self.assertEqual((verdict.decision, verdict.rule), (ASK, None))

    def test_regex_tool_names_agent_and_arg_patterns(self):
        policy = Policy([
            Rule("re:^fhir_(create|update)$", ASK, agent="fraud*"),
            Rule("*", DENY, args={"path": "re:\\.env$"}),
            Rule("submit", ASK, args={"confirm": True}),
            Rule("submit", ALLOW),
            Rule("search", ALLOW, args={"q": "patient*", "limit": None}),
        ], default=DENY)
        self.assertEqual(policy.evaluate("fhir_update", {}, agent="fraud").decision, ASK)
        self.assertEqual(policy.evaluate("fhir_update", {}, agent="benefits").decision, DENY)
        self.assertEqual(policy.evaluate("open_file", {"path": "/app/.env"}).decision, DENY)
        self.assertEqual(policy.evaluate("submit", {"confirm": True}).decision, ASK)
        self.assertEqual(policy.evaluate("submit", {"confirm": False}).decision, ALLOW)
        self.assertEqual(policy.evaluate("search", {"q": "patient 7"}).decision, ALLOW)
        self.assertEqual(policy.evaluate("search", {"q": "patient 7", "limit": 5}).decision, DENY)
        self.assertEqual(policy.evaluate("search", None).decision, DENY)  # bad args: no match, default

    def test_rule_with_python_predicate(self):
        policy = Policy([Rule("pay", ALLOW, when=lambda name, args, agent: args.get("amount", 0) < 100)], default=DENY)
        self.assertEqual(policy.evaluate("pay", {"amount": 5}).decision, ALLOW)
        self.assertEqual(policy.evaluate("pay", {"amount": 500}).decision, DENY)

    def test_invalid_decisions_are_rejected(self):
        with self.assertRaises(ValueError):
            Rule("x", "maybe")
        with self.assertRaises(ValueError):
            Policy(default="sure")
        with self.assertRaises(ValueError):
            policy_from_dict({"rules": [{"tool": "x", "decision": "allow", "typo": 1}]})

    def test_yaml_policy(self):
        policy = load_policy(Path(__file__).parent / "examples" / "example.yaml")
        self.assertEqual(policy.evaluate("fhir_read", {}).decision, ALLOW)
        self.assertEqual(policy.evaluate("fhir_delete", {}).decision, ASK)
        self.assertEqual(policy.evaluate("anything", {"path": "~/.ssh/id_rsa"}).decision, DENY)
        verdict = policy.evaluate("submit_enrollment_change", {"confirm": True})
        self.assertEqual((verdict.decision, verdict.message), (ASK, "The member declined; nothing was submitted."))
        self.assertEqual(policy.evaluate("shell", {}, agent="fraud").decision, ASK)
        self.assertEqual(policy.default, ASK)


class DefaultPolicyTests(unittest.TestCase):
    def test_fhir_reads_allowed_writes_ask_unknown_ask(self):
        for policy in (fhir_agent_policy(), fraud_policy(), pharmacy_policy()):
            self.assertEqual(policy.evaluate("fhir_search", {"resource_type": "Patient"}).decision, ALLOW)
            self.assertEqual(policy.evaluate("fhir_update", {}).decision, ASK)
            self.assertEqual(policy.evaluate("shell", {"command": "ls"}).decision, ASK)
            self.assertEqual(policy.evaluate("brand_new_tool", {}).decision, ASK)
            self.assertEqual(policy.evaluate("fhir_read", {"path": ".env"}).decision, DENY)

    def test_agent_specific_tools(self):
        self.assertEqual(fraud_policy().evaluate("provider_daily_load", {"provider": "x"}).decision, ALLOW)
        self.assertEqual(fhir_agent_policy().evaluate("provider_daily_load", {}).decision, ASK)
        self.assertEqual(fraud_policy(["learned_x"]).evaluate("learned_x", {}).decision, ALLOW)
        self.assertEqual(pharmacy_policy().evaluate("openfda_search_recalls", {}).decision, ALLOW)

    def test_benefits_write_needs_approval_only_when_confirmed(self):
        policy = benefits_policy()
        self.assertEqual(policy.evaluate("submit_enrollment_change", {"confirm": True}).decision, ASK)
        self.assertEqual(policy.evaluate("submit_enrollment_change", {"confirm": False}).decision, ALLOW)
        self.assertEqual(policy.evaluate("premium_quote", {}).decision, ALLOW)
        self.assertEqual(policy.evaluate("delete_member", {}).decision, ASK)


class ScriptInspectionTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def script(self, name: str, text: str) -> str:
        (self.dir / name).write_text(text)
        return name

    def findings(self, command: str) -> list[str]:
        return inspect_command(command, self.dir)

    def test_clean_python_script(self):
        name = self.script("ok.py", "import json\nprint(json.dumps({'a': 1}))\n")
        self.assertEqual(self.findings(f"python3 {name} --flag"), [])

    def test_python_deletion_network_secrets_and_subprocess_rm(self):
        cases = {
            "del.py": ("import shutil\nshutil.rmtree('/tmp/x')\n", "file deletion"),
            "unlink.py": ("from pathlib import Path\nPath('a').unlink()\n", "file deletion"),
            "net.py": ("import requests\nrequests.post('https://x', data='y')\n", "network egress"),
            "sock.py": ("from socket import socket\n", "network egress"),
            "env.py": ("print(open('.env').read())\n", "reads secrets"),
            "ssh.py": ("import os\nopen(os.path.expanduser('~/.ssh/id_rsa'))\n", "reads secrets"),
            "rm.py": ("import subprocess\nsubprocess.run(['rm', '-rf', 'data'])\n", "through a subprocess"),
            "sys.py": ("import os\nos.system('rm -rf /tmp/y')\n", "through a subprocess"),
        }
        for name, (source, expected) in cases.items():
            with self.subTest(name=name):
                found = self.findings(f"python {self.script(name, source)}")
                self.assertTrue(any(expected in f for f in found), found)

    def test_shell_and_node_scripts(self):
        sh = self.script("clean.sh", "#!/bin/sh\nrm -rf build\n")
        self.assertTrue(any("file deletion" in f for f in self.findings(f"bash {sh}")))
        up = self.script("up.sh", "curl -d @data.json https://example.com\n")
        self.assertTrue(any("network egress" in f for f in self.findings(f"sh {up}")))
        js = self.script("x.js", "const fs = require('fs'); fs.unlinkSync('a'); fetch('https://x')\n")
        found = self.findings(f"node {js}")
        self.assertTrue(any("file deletion" in f for f in found) and any("network egress" in f for f in found), found)
        self.assertEqual(self.findings(f"node {self.script('ok.js', 'console.log(1 + 1)')}"), [])

    def test_inline_code_chains_and_direct_execution(self):
        self.assertTrue(self.findings("python -c \"import os; os.remove('x')\""))
        self.assertTrue(self.findings("bash -c 'cat ~/.ssh/id_rsa'"))
        ok = self.script("ok.py", "print(1)\n")
        bad = self.script("bad.py", "import shutil\nshutil.rmtree('/')\n")
        self.assertTrue(self.findings(f"python {ok} && python {bad}"))
        self.assertTrue(self.findings(f"./{bad}"))
        self.assertTrue(self.findings("ls; rm -rf /"))
        self.assertEqual(self.findings("ls -la"), [])

    def test_fails_closed_on_unreadable_or_unparseable_input(self):
        self.assertTrue(any("could not read" in f for f in self.findings("python missing.py")))
        broken = self.script("broken.py", "def (:\n")
        self.assertTrue(any("could not parse Python" in f for f in self.findings(f"python {broken}")))
        self.assertTrue(any("could not parse the command" in f for f in self.findings("python 'unterminated")))
        (self.dir / "bin.py").write_bytes(b"\xff\xfe\x00")
        self.assertTrue(any("could not read" in f for f in self.findings("python bin.py")))

    def test_only_command_like_arguments_are_inspected(self):
        self.assertEqual(inspect_call({"query": "python missing.py"}, self.dir), [])
        self.assertTrue(inspect_call({"command": "python missing.py"}, self.dir))
        self.assertTrue(inspect_call({"command": ["python", "missing.py"]}, self.dir))
        self.assertEqual(inspect_call(None, self.dir), [])


class MiddlewareTests(unittest.TestCase):
    def setUp(self):
        RAN.clear()
        self.audit = MemoryAuditLog()
        self.policy = Policy([Rule("fhir_read", ALLOW), Rule("fhir_delete", ASK, "write", message="Not deleted."),
                              Rule("shell", ALLOW)], default=DENY)

    def agent(self, replies, **kwargs):
        model = ScriptedChatModel(replies=list(replies))
        checkpointer = kwargs.pop("checkpointer", None)
        permissions = PermissionMiddleware(kwargs.pop("policy", self.policy), agent_name="test", audit=self.audit,
                                           **kwargs)
        return model, create_agent(model, [fhir_read, fhir_delete, shell], middleware=[permissions],
                                   checkpointer=checkpointer)

    def run_async(self, app, messages, config=None):
        return asyncio.run(app.ainvoke({"messages": messages}, config))

    def test_allow_runs_the_tool(self):
        _, app = self.agent([call("fhir_read", {"resource_type": "Patient", "id": "1"}), AIMessage("done")])
        state = self.run_async(app, [("user", "q")])
        self.assertEqual(RAN, ["fhir_read"])
        self.assertEqual(tool_messages(state)[0].content, "Patient/1")
        self.assertEqual(self.audit.records[0]["decision"], ALLOW)

    def test_deny_returns_error_tool_message_and_agent_continues(self):
        model, app = self.agent([call("unknown_tool", {}), AIMessage("I can't do that.")])
        state = self.run_async(app, [("user", "q")])
        denied = tool_messages(state)[0]
        self.assertEqual(denied.status, "error")
        self.assertIn("Permission denied for unknown_tool", denied.content)
        self.assertEqual(state["messages"][-1].content, "I can't do that.")
        self.assertEqual(RAN, [])
        self.assertEqual(self.audit.records[0]["decision"], DENY)

    def test_sync_invoke_path(self):
        _, app = self.agent([call("unknown_tool", {}), AIMessage("ok")])
        state = app.invoke({"messages": [("user", "q")]})
        self.assertIn("Permission denied", tool_messages(state)[0].content)

    def test_ask_without_approver_is_deny(self):
        _, app = self.agent([call("fhir_delete", {"resource_type": "Patient", "id": "1"}), AIMessage("ok")])
        state = self.run_async(app, [("user", "q")])
        self.assertEqual(tool_messages(state)[0].content, "Not deleted.")
        self.assertEqual(RAN, [])
        self.assertEqual(self.audit.records[0]["via"], "non-interactive")

    def test_ask_with_sync_and_async_approver(self):
        args = {"resource_type": "Patient", "id": "1"}
        seen = []
        _, app = self.agent([call("fhir_delete", args), AIMessage("ok")],
                            approver=lambda name, a, reason: seen.append((name, a, reason)) or True)
        self.run_async(app, [("user", "q")])
        self.assertEqual(RAN, ["fhir_delete"])
        self.assertEqual(seen[0][:2], ("fhir_delete", args))

        async def no(name, a, reason):
            return False
        RAN.clear()
        _, app = self.agent([call("fhir_delete", args), AIMessage("ok")], approver=no)
        state = self.run_async(app, [("user", "q")])
        self.assertEqual((RAN, tool_messages(state)[0].content), ([], "Not deleted."))

    def test_ask_interactive_interrupts_and_resumes(self):
        args = {"resource_type": "Patient", "id": "1"}
        for answer, ran in ((True, ["fhir_delete"]), ({"approve": False}, [])):
            with self.subTest(answer=answer):
                RAN.clear()
                _, app = self.agent([call("fhir_delete", args), AIMessage("ok")], interactive=True,
                                    checkpointer=InMemorySaver())
                config = {"configurable": {"thread_id": f"t-{answer}"}}
                first = self.run_async(app, [("user", "q")], config)
                request = first["__interrupt__"][0].value
                self.assertEqual((request["type"], request["tool"], request["args"]),
                                 ("permission_request", "fhir_delete", args))
                self.assertEqual(RAN, [])
                asyncio.run(app.ainvoke(Command(resume=answer), config))
                self.assertEqual(RAN, ran)

    def test_policy_errors_fail_closed(self):
        def boom(name, args, agent):
            raise RuntimeError("broken rule")
        policy = Policy([Rule("fhir_read", ALLOW, when=boom)], default=ALLOW)
        _, app = self.agent([call("fhir_read", {"resource_type": "Patient", "id": "1"}), AIMessage("ok")],
                            policy=policy)
        state = self.run_async(app, [("user", "q")])
        self.assertIn("failing closed", tool_messages(state)[0].content)
        self.assertEqual(RAN, [])
        self.assertEqual(self.audit.records[-1]["via"], "fail-closed")

    def test_approver_and_audit_errors_fail_closed(self):
        def explode(*_):
            raise ValueError("approver crashed")
        _, app = self.agent([call("fhir_delete", {"resource_type": "P", "id": "1"}), AIMessage("ok")], approver=explode)
        self.assertIn("failing closed", tool_messages(self.run_async(app, [("user", "q")]))[0].content)

        class BrokenAudit(MemoryAuditLog):
            def record(self, **fields):
                raise OSError("disk full")
        model = ScriptedChatModel(replies=[call("fhir_read", {"resource_type": "P", "id": "1"}), AIMessage("ok")])
        app = create_agent(model, [fhir_read], middleware=[PermissionMiddleware(self.policy, audit=BrokenAudit())])
        state = self.run_async(app, [("user", "q")])
        self.assertIn("failing closed", tool_messages(state)[0].content)
        self.assertEqual(RAN, [])

    def test_script_inspection_downgrades_allow_to_deny(self):
        workdir = Path(tempfile.mkdtemp())
        (workdir / "wipe.py").write_text("import shutil\nshutil.rmtree('/data')\n")
        (workdir / "ok.py").write_text("print('hi')\n")
        _, app = self.agent([call("shell", {"command": "python wipe.py"}, "a"),
                             call("shell", {"command": "python ok.py"}, "b"), AIMessage("ok")], workdir=workdir)
        state = self.run_async(app, [("user", "q")])
        denied, allowed = tool_messages(state)
        self.assertIn("script inspection", denied.content)
        self.assertIn("file deletion", denied.content)
        self.assertEqual(allowed.content, "ran")
        self.assertEqual(RAN, ["shell"])

    def test_audit_log_writes_jsonl(self):
        from agent_permissions import AuditLog
        path = Path(tempfile.mkdtemp()) / "audit.jsonl"
        model = ScriptedChatModel(replies=[call("unknown", {"x": 1}), AIMessage("ok")])
        app = create_agent(model, [fhir_read], middleware=[PermissionMiddleware(self.policy, agent_name="a",
                                                                                  audit=AuditLog(path))])
        self.run_async(app, [("user", "q")])
        import json
        entry = json.loads(path.read_text().splitlines()[0])
        self.assertEqual((entry["agent"], entry["tool"], entry["decision"], entry["args"]), ("a", "unknown", DENY, {"x": 1}))


if __name__ == "__main__":
    unittest.main()
