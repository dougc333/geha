import inspect
from support import Fixture, CFG, workflow, resume


class DuplicateRequestTests(Fixture):
    def test_sequential_duplicate_is_rejected_without_new_checkpoints(self):
        self.start()

        with workflow(self.db, self.base) as g:
            resume(g, "case", "approve", "Verified")
            before = [s.config for s in g.get_state_history(CFG)]
            for action in ("approve", "reject"):
                with self.assertRaisesRegex(ValueError, "not waiting"):
                    resume(g, "case", action, "Duplicate")
            self.assertEqual([s.config for s in g.get_state_history(CFG)], before)

    def test_persistent_request_id_contract(self):
        # A deliberately strict requirement test: absence is a failure, not a skip.
        self.assertIn(
            "request_id",
            inspect.signature(resume).parameters,
            "Persistent request-ID idempotency is not implemented in resume()",
        )
        self.start()
        with workflow(self.db, self.base) as g:
            first = resume(g, "case", "approve", "Verified", request_id="request-1")
            before = [s.config for s in g.get_state_history(CFG)]
        with workflow(self.db, self.base) as g:
            self.assertEqual(
                resume(g, "case", "approve", "Verified", request_id="request-1"), first
            )
            self.assertEqual([s.config for s in g.get_state_history(CFG)], before)
            with self.assertRaises(ValueError):
                resume(g, "case", "reject", "Different payload", request_id="request-1")
