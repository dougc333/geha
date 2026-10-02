"""Tests for the Vercel version of the benefits chatbot.

    cd /Users/dc/geha/e2e_RAG/benefits_vercel && ../../.venv/bin/python -m unittest test_benefits_vercel
"""

import json
import subprocess
import sys
import threading
import unittest
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
EVALS = HERE.parent / "evals"
sys.path.insert(0, str(HERE))

from api.chat import chat, clean_state  # noqa: E402
from scripts.build import MODULES  # noqa: E402


class BuildTests(unittest.TestCase):
    def test_bot_modules_match_src(self):
        for name in MODULES:
            with self.subTest(module=name):
                self.assertEqual((HERE / "benefits" / name).read_text(), (SRC / name).read_text(),
                                 "stale copy: run scripts/build.py")

    def test_tables_json_matches_the_pdfs(self):
        sys.path.insert(0, str(SRC))
        try:
            from dental_tables import GUIDE, DentalTables
            from medical_tables import GUIDE as MEDICAL_GUIDE, MedicalTables
        finally:
            sys.path.remove(str(SRC))
        if not (GUIDE.exists() and MEDICAL_GUIDE.exists()):
            self.skipTest("GEHA PDFs not found")
        shipped = json.loads((HERE / "tables.json").read_text())
        fresh = json.loads(json.dumps({"dental": DentalTables().to_dict(), "medical": MedicalTables().to_dict()}))
        self.assertEqual(shipped, fresh, "stale tables.json: run scripts/build.py")

    def test_function_runs_without_pymupdf_or_pdfs(self):
        code = ("import sys; sys.modules['pymupdf'] = None; sys.path.insert(0, '.'); "
                "from api.chat import chat; print(chat({'message': 'medical, employed, self only, elevate'})['reply'])")
        out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True,
                             env={"DENTAL_GUIDE": "/nonexistent.pdf", "FEHB_DIR": "/nonexistent", "PATH": ""})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("$77.92 biweekly", out.stdout)


class ApiTests(unittest.TestCase):
    def test_state_round_trip_reaches_a_quote(self):
        state = None
        for message in ["dental and medical", "20500", "retired", "me and my wife", "high", "elevate plus"]:
            out = chat({"message": message, "state": json.loads(json.dumps(state)) if state else {}})
            state = out["state"]
        self.assertIn("Total: $1,086.93 monthly", out["reply"])
        self.assertEqual(out["slots"]["medical_plan"], "Elevate Plus")

    def test_conversation_test_set_matches_the_stateful_bot(self):
        results = json.loads((EVALS / "benefits_conversations_results.json").read_text())["results"]
        for case in results:
            state = {}
            for turn in case["transcript"]:
                out = chat({"message": turn["member"], "state": state})
                state = json.loads(json.dumps(out["state"]))
                with self.subTest(conversation=case["id"], message=turn["member"]):
                    self.assertEqual(out["reply"], turn["bot"])

    def test_bad_requests(self):
        for body in ({}, {"message": ""}, {"message": "x" * 501}, {"message": 5}):
            with self.subTest(body=str(body)[:40]):
                with self.assertRaises(ValueError):
                    chat(body)

    def test_untrusted_state_is_cleaned(self):
        raw = {"slots": {"zip": "94105", "rate_code": 99, "evil": "x", "line": "x" * 500, "status": "RETIRED"},
               "candidates": ["CA", "<script>"], "topics": ["dental:orthodontics", "rm -rf"], "stage": "nope",
               "quoted": 7, "extra": {"a": 1}}
        self.assertEqual(clean_state(raw), {"slots": {"zip": "94105", "status": "RETIRED"}, "candidates": ["CA"],
                                            "topics": ["dental:orthodontics"]})
        self.assertEqual(clean_state("junk"), {})


class LocalServerTests(unittest.TestCase):
    def test_page_and_api_over_http(self):
        from local_server import LocalHandler
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(LocalHandler, directory=str(HERE / "public")))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            page = urllib.request.urlopen(f"{base}/index.html").read().decode()
            self.assertIn("/api/chat", page)
            req = urllib.request.Request(f"{base}/api/chat", data=json.dumps({"message": "hi"}).encode(),
                                         headers={"Content-Type": "application/json"})
            self.assertIn("dental, medical, or both", json.load(urllib.request.urlopen(req))["reply"])
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
