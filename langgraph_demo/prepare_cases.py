"""Prepare one stable saved explanation-review thread per synthetic claim."""

import uuid
from demo import ROOT, load_inputs, workflow


def prepare(db, base):
    claims, trails, _, _ = load_inputs(base)
    created = 0
    with workflow(db, base) as g:
        for claim in sorted(claims):
            if claim not in trails:
                raise ValueError(f"Missing audit trail for {claim}")
            tid = str(
                uuid.uuid5(uuid.NAMESPACE_URL, "geha-demo/prepared-review/" + claim)
            )
            cfg = {"configurable": {"thread_id": tid}}
            if g.get_state(cfg).values:
                continue
            g.invoke({"claim_id": claim, "actor": "demo_operator"}, cfg)
            assert g.get_state(cfg).next == ("review",)
            created += 1
    return created


if __name__ == "__main__":
    print(
        "Prepared new reviews:", prepare(ROOT / "data/checkpoints.sqlite", ROOT.parent)
    )
