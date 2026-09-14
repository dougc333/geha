"""Isolated regression tests: fresh reviews and persisted reviews for 20 claims.

All inputs and checkpoints are temporary; no real demo cases are changed.
"""

import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from demo import workflow, resume
from prepare_cases import prepare


class ReviewCasesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.db = self.base / "checkpoints.sqlite"
        folder = self.base / "agentic_simulation/claims"
        folder.mkdir(parents=True)
        self.ids = [f"CLM-{100000 + i}" for i in range(20)]
        statuses = ["PENDING_REVIEW", "PAID", "DENIED", "PARTIAL"]
        self.statuses = {cid: statuses[i % 4] for i, cid in enumerate(self.ids)}
        claims = [
            {
                "claim_id": cid,
                "member_id": f"M{i}",
                "plan": "Synthetic",
                "status": self.statuses[cid],
            }
            for i, cid in enumerate(self.ids)
        ]
        trails = [
            {
                "claim_id": cid,
                "final_status": self.statuses[cid],
                "stages": [{"status": "PENDING", "note": "Requires prior auth review"}]
                if self.statuses[cid] == "PENDING_REVIEW"
                else [],
            }
            for cid in self.ids
        ]
        refs = self.base / "agentic_reference/data"
        refs.mkdir(parents=True)
        self.sources = {
            folder / "claims.json": json.dumps(claims),
            folder / "audit_trails.json": json.dumps(trails),
            refs / "public_reference.json": json.dumps(
                [
                    {
                        "text": "Contact the provider for assistance.",
                        "metadata": {
                            "visibility": "public",
                            "topic": "prior_authorization",
                        },
                        "source": {
                            "title": "Reference",
                            "url": "https://www.geha.com/",
                        },
                    }
                ]
            ),
        }
        for path, text in self.sources.items():
            path.write_text(text)

    @staticmethod
    def config(tid):
        return {"configurable": {"thread_id": tid}}

    @staticmethod
    def prepared_id(cid):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "geha-demo/prepared-review/" + cid))

    def assert_sources_unchanged(self):
        for path, text in self.sources.items():
            self.assertEqual(path.read_text(), text)

    def test_new_reviews_for_all_20_pause_without_changing_claim_status(self):
        with workflow(self.db, self.base) as g:
            for cid in self.ids:
                with self.subTest(claim=cid):
                    cfg = self.config(str(uuid.uuid4()))
                    g.invoke({"claim_id": cid, "actor": "demo_operator"}, cfg)
                    snap = g.get_state(cfg)
                    self.assertEqual(snap.next, ("review",))
                    self.assertEqual(snap.values["facts"]["status"], self.statuses[cid])
                    self.assertEqual(snap.values["answer"], "")
        self.assert_sources_unchanged()

    def test_two_new_reviews_for_same_claim_have_independent_histories(self):
        first, second = str(uuid.uuid4()), str(uuid.uuid4())
        with workflow(self.db, self.base) as g:
            for tid in [first, second]:
                g.invoke(
                    {"claim_id": self.ids[0], "actor": "demo_operator"},
                    self.config(tid),
                )
            resume(g, first, "approve", "Verified", edited_text="Reviewed explanation")
            self.assertFalse(g.get_state(self.config(first)).next)
            self.assertEqual(g.get_state(self.config(second)).next, ("review",))
            self.assertNotIn("review", g.get_state(self.config(second)).values)

    def test_all_20_saved_reviews_survive_reopen_and_keep_history(self):
        self.assertEqual(prepare(self.db, self.base), 20)
        with workflow(self.db, self.base) as g:
            before = {
                cid: list(g.get_state_history(self.config(self.prepared_id(cid))))
                for cid in self.ids
            }
        with workflow(self.db, self.base) as g:
            for cid in self.ids:
                with self.subTest(claim=cid):
                    cfg = self.config(self.prepared_id(cid))
                    self.assertEqual(g.get_state(cfg).next, ("review",))
                    self.assertEqual(g.get_state(cfg).values["claim_id"], cid)
                    after = list(g.get_state_history(cfg))
                    self.assertEqual(
                        [s.config for s in after], [s.config for s in before[cid]]
                    )

    def test_prepare_is_idempotent_and_preserves_completed_and_other_threads(self):
        self.assertEqual(prepare(self.db, self.base), 20)
        other = "existing-manual-review"
        with workflow(self.db, self.base) as g:
            g.invoke(
                {"claim_id": self.ids[0], "actor": "demo_operator"}, self.config(other)
            )
            resume(g, self.prepared_id(self.ids[0]), "reject", "Insufficient evidence")
            before = g.get_state(self.config(self.prepared_id(self.ids[0])))
        self.assertEqual(prepare(self.db, self.base), 0)
        with workflow(self.db, self.base) as g:
            after = g.get_state(self.config(self.prepared_id(self.ids[0])))
            self.assertEqual(after.config, before.config)
            self.assertEqual(after.values, before.values)
            self.assertEqual(g.get_state(self.config(other)).next, ("review",))
        self.assert_sources_unchanged()

    def test_reopened_reviews_can_approve_or_reject_all_20_without_claim_mutation(self):
        prepare(self.db, self.base)
        for i, cid in enumerate(self.ids):
            with self.subTest(claim=cid), workflow(self.db, self.base) as g:
                action = "approve" if i % 2 == 0 else "reject"
                tid = self.prepared_id(cid)
                result = resume(
                    g, tid, action, "Checked evidence", edited_text="Reviewed text"
                )
                self.assertEqual(result["review"]["action"], action)
                self.assertEqual(result["facts"]["status"], self.statuses[cid])
                self.assertEqual(
                    result["answer"],
                    "Reviewed text"
                    if action == "approve"
                    else "Explanation rejected; no response released.",
                )
                self.assertFalse(g.get_state(self.config(tid)).next)
                with self.assertRaises(ValueError):
                    resume(g, tid, action, "Duplicate submission")
        self.assert_sources_unchanged()

    def test_expanded_operator_access_does_not_expand_member_or_outsider_access(self):
        with workflow(self.db, self.base) as g:
            for actor, cid in [
                ("member", self.ids[1]),
                ("outsider", self.ids[0]),
                ("demo_operator", "CLM-UNKNOWN"),
            ]:
                with self.subTest(actor=actor, claim=cid):
                    cfg = self.config(str(uuid.uuid4()))
                    result = g.invoke({"claim_id": cid, "actor": actor}, cfg)
                    self.assertFalse(result["authorized"])
                    self.assertNotIn("facts", result)
                    self.assertFalse(g.get_state(cfg).next)

    def test_streamlit_start_refresh_and_reopen_use_automatic_ids(self):
        from streamlit.testing.v1 import AppTest

        prepare(self.db, self.base)
        with patch.dict(
            os.environ, {"GEHA_DEMO_BASE": str(self.base), "GEHA_DEMO_DB": str(self.db)}
        ):
            app = str(Path(__file__).with_name("app.py"))
            a = AppTest.from_file(app, default_timeout=30).run()
            self.assertFalse(a.exception)
            claim_box = next(x for x in a.selectbox if x.label == "Synthetic claim")
            self.assertEqual(len(claim_box.options), 20)
            claim_box.select(self.ids[-1])
            next(b for b in a.button if b.label == "Start new review").click().run()
            self.assertFalse(a.exception)
            tid = a.session_state["case_select"]
            self.assertEqual(uuid.UUID(tid).version, 4)
            picker = next(x for x in a.selectbox if x.label == "Reopen a case")
            self.assertEqual(len(picker.options), 21)
            a.run()
            self.assertEqual(a.session_state["case_select"], tid)
            self.assertEqual(
                len(next(x for x in a.selectbox if x.label == "Reopen a case").options),
                21,
            )
            b = AppTest.from_file(app, default_timeout=30).run()
            self.assertFalse(b.exception)
            next(x for x in b.selectbox if x.label == "Reopen a case").select(tid).run()
            self.assertEqual(b.session_state["case_select"], tid)
            with workflow(self.db, self.base) as g:
                self.assertEqual(
                    g.get_state(self.config(tid)).values["claim_id"], self.ids[-1]
                )
            next(x for x in b.text_input if x.label == "Reason (required)").set_value(
                "Verified"
            )
            next(x for x in b.button if x.label == "Submit review").click().run()
            self.assertFalse(b.exception)
            self.assertTrue(any("Review completed" in x.value for x in b.success))


if __name__ == "__main__":
    unittest.main()
