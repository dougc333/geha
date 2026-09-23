from support import Fixture


class ConcurrentReviewTests(Fixture):
    def test_only_one_process_may_accept_a_review(self):
        self.start()
        first, p1 = self.launch("race", "approve")
        second, p2 = self.launch("race", "reject")
        self.assertEqual(self.receive(p1, "ready"), ("review",))
        self.assertEqual(self.receive(p2, "ready"), ("review",))
        p1.send("go")
        p2.send("go")
        results = [self.receive(p1, "result"), self.receive(p2, "result")]
        first.join(5)
        second.join(5)
        self.assertEqual(first.exitcode, 0)
        self.assertEqual(second.exitcode, 0)
        self.assertEqual(
            sum(r["accepted"] for r in results),
            1,
            f"Cross-process review exclusivity is missing: {results}",
        )
