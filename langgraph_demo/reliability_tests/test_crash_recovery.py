from support import Fixture, CFG, workflow, resume


class CrashRecoveryTests(Fixture):
    def test_kill_after_interrupt_commit(self):
        self.kill_at_gate("start_crash")
        self.assertEqual(self.inspect()["next"], ("review",))
        with workflow(self.db, self.base) as g:
            result = resume(g, "case", "approve", "Restarted")
            self.assertEqual(result["review"]["action"], "approve")

    def test_kill_before_resume_checkpoint_commit(self):
        self.start()
        self.kill_at_gate("before_commit")
        proc, pipe = self.launch("recover")
        result = self.receive(pipe, "result")
        proc.join(5)
        self.assertEqual(proc.exitcode, 0)
        self.assertFalse(result["next"])
        self.assertEqual(result["state"]["review"]["action"], "approve")
        self.assertEqual(result["state"]["facts"]["status"], "PENDING_REVIEW")

    def test_kill_after_completion_before_client_ack(self):
        self.start()
        self.kill_at_gate("complete_crash")
        before = self.inspect()
        self.assertFalse(before["next"])
        with workflow(self.db, self.base) as g:
            with self.assertRaisesRegex(ValueError, "not waiting"):
                resume(g, "case", "approve", "Retry after lost response")
        self.assertEqual(self.inspect(), before)
