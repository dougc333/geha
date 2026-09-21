"""Local synthetic workflow: authorize, lookup, retrieve, draft, interrupt, release."""

import argparse
import fcntl
import hashlib
import json
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """Identity verified by the caller's authentication boundary.

    This demo has no identity provider, so its built-in identity is synthetic. A
    deployed API must construct this value only after verifying an OIDC/JWT token.
    """

    subject: str
    issuer: str
    roles: frozenset[str]

    def __post_init__(self):
        if not self.subject.strip() or not self.issuer.strip():
            raise ValueError("Authenticated identity requires subject and issuer")


DEMO_REVIEWER = AuthenticatedIdentity( 
    subject="demo-reviewer",
    issuer="local-synthetic-demo",
    roles=frozenset({"reviewer"}),
)
_MEMORY_RESUME_LOCK = threading.RLock()


class State(TypedDict, total=False):
    claim_id: str
    actor: str
    authorized: bool
    facts: dict
    evidence: list
    draft: str
    review: dict
    audit_event: dict
    answer: str


def load_inputs(base):
    folder = Path(base) / "demo_data"
    claims = {
        c["claim_id"]: c for c in json.loads((folder / "claims.json").read_text())
    }
    trails = {
        c["claim_id"]: c for c in json.loads((folder / "audit_trails.json").read_text())
    }
    refs = json.loads((folder / "public_reference.json").read_text())
    pending = sorted(
        k
        for k, v in trails.items()
        if v["final_status"] == "PENDING_REVIEW" and k in claims
    )
    if not pending:
        raise ValueError("No synthetic pending claim is available")
    return claims, trails, refs, pending[0]


def make_graph(saver, base):
    claims, trails, refs, example = load_inputs(base)
    # Fixed fixture identity. No caller-supplied member scopes are accepted.
    member = claims[example]["member_id"]

    def authorize(s):
        claim = claims.get(s["claim_id"])
        # demo_operator is an explicit synthetic-only fixture, not real staff authentication.
        allowed = bool(
            claim
            and (
                s["actor"] == "demo_operator"
                or (s["actor"] == "member" and claim["member_id"] == member)
            )
        )
        return {
            "authorized": allowed,
            "answer": "" if allowed else "Claim not found or access denied.",
        }

    def lookup(s):
        c, t = claims[s["claim_id"]], trails.get(s["claim_id"])
        if not t:
            raise ValueError("Missing simulation audit trail")
        reasons = [
            x["note"] for x in t["stages"] if x["status"] in ("PENDING", "DENY", "FLAG")
        ]
        return {
            "facts": {
                "claim_id": s["claim_id"],
                "status": t["final_status"],
                "plan": c["plan"],
                "reasons": reasons,
                "source": str(Path(base) / "demo_data/audit_trails.json"),
            }
        }

    def retrieve(s):
        topic = (
            "prior_authorization"
            if any("auth" in x.lower() for x in s["facts"]["reasons"])
            else "claim_submission"
        )
        return {
            "evidence": [
                r
                for r in refs
                if r["metadata"].get("visibility") == "public"
                and r["metadata"].get("topic") == topic
            ][:2]
        }

    def draft(s):
        f = s["facts"]
        reasons = "; ".join(f["reasons"]) or "No blocking reason is recorded."
        text = f"SIMULATION ONLY. Claim {f['claim_id']} has recorded status {f['status']}. Recorded reason: {reasons}\n"
        text += "No missing-document checklist is recorded; ask the reviewer to identify any required evidence.\n"
        text += (
            "General reference guidance (not plan/year-specific coverage evidence):\n"
        )
        text += "\n".join(
            f"{r['text']} [{r['source']['title']}]({r['source']['url']})"
            for r in s["evidence"]
        )
        if not s["evidence"]:
            text += (
                "No relevant reference found; reviewer must supply verified guidance."
            )
        return {"draft": text}

    def review(s):
        decision = interrupt(
            {
                "instruction": "Review the explanation, not the claim outcome.",
                "draft": s["draft"],
            }
        )
        if (
            "reviewer" not in decision.get("actor_roles", [])
            or decision.get("action") not in ("approve", "reject")
            or not decision.get("reason", "").strip()
        ):
            raise ValueError("Authenticated reviewer, action, and reason required")
        audit_event = {
            "event_id": decision["event_id"],
            "event_type": f"review.{decision['action']}",
            "occurred_at": decision["occurred_at"],
            "actor_id": decision["actor_id"],
            "actor_issuer": decision["actor_issuer"],
            "subject_id": s["claim_id"],
            "thread_id": decision["thread_id"],
            "request_id": decision["request_id"],
            "payload_hash": decision["payload_hash"],
        }
        # LangGraph persists both channel writes from this node together. The
        # decision and its audit event therefore cannot diverge in graph state.
        return {"review": decision, "audit_event": audit_event}

    def release(s):
        r = s["review"]
        text = (
            (r.get("edited_text") or s["draft"])
            if r["action"] == "approve"
            else "Explanation rejected; no response released."
        )
        return {"answer": text}

    g = StateGraph(State)
    for name, fn in [
        ("authorize", authorize),
        ("lookup", lookup),
        ("retrieve", retrieve),
        ("draft", draft),
        ("review", review),
        ("release", release),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "authorize")
    g.add_conditional_edges("authorize", lambda s: "lookup" if s["authorized"] else END)
    for a, b in [
        ("lookup", "retrieve"),
        ("retrieve", "draft"),
        ("draft", "review"),
        ("review", "release"),
        ("release", END),
    ]:
        g.add_edge(a, b)
    return g.compile(checkpointer=saver)


@contextmanager
def workflow(db, base):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(db)) as saver:
        yield make_graph(saver, base)


def _resume_payload_hash(thread, action, reason, edited_text, identity):
    payload = {
        "thread_id": str(thread),
        "action": action,
        "reason": reason,
        "edited_text": edited_text,
        "actor_id": identity.subject,
        "actor_issuer": identity.issuer,
        "actor_roles": sorted(identity.roles),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@contextmanager
def _exclusive_resume(graph):
    """Serialize resume commits across processes sharing this SQLite database."""
    checkpointer = getattr(graph, "checkpointer", None)
    conn = getattr(checkpointer, "conn", None)
    if conn is None:
        raise RuntimeError(
            "resume() requires a checkpointer with a database connection"
        )
    row = next(
        (r for r in conn.execute("PRAGMA database_list") if r[1] == "main"), None
    )
    db_path = row[2] if row else ""
    if not db_path:
        with _MEMORY_RESUME_LOCK:
            yield
        return
    # flock is deliberately local to the SQLite demo. EKS must replace this with
    # a PostgreSQL transaction/advisory lock or compare-and-set operation.
    lock_path = Path(str(db_path) + ".resume.lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _replay_completed(snap, request_id, payload_hash):
    review = snap.values.get("review")
    if review and review.get("request_id") == request_id:
        if review.get("payload_hash") != payload_hash:
            raise ValueError(
                "request_id was already used with a different review payload"
            )
        return snap.values
    raise ValueError("Thread is not waiting for review")


def resume(
    graph,
    thread,
    action,
    reason,
    edited_text=None,
    *,
    request_id=None,
    identity=DEMO_REVIEWER,
    reviewer=None,
    callbacks=None,
    run_name=None,
    tags=None,
    metadata=None,
):
    if reviewer is not None:
        raise ValueError(
            "Caller-supplied reviewer labels are not authenticated identities"
        )
    if (
        not isinstance(identity, AuthenticatedIdentity)
        or "reviewer" not in identity.roles
    ):
        raise ValueError("An authenticated identity with the reviewer role is required")
    if (
        action not in ("approve", "reject")
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise ValueError("Action and nonempty reason required")
    if request_id is None:
        request_id = str(uuid.uuid4())
    if (
        not isinstance(request_id, str)
        or not request_id.strip()
        or len(request_id) > 255
    ):
        raise ValueError(
            "request_id must be a nonempty string of at most 255 characters"
        )
    request_id = request_id.strip()
    payload_hash = _resume_payload_hash(thread, action, reason, edited_text, identity)
    config = {"configurable": {"thread_id": thread}}
    if callbacks is not None:
        config["callbacks"] = callbacks
    if run_name is not None:
        config["run_name"] = run_name
    if tags is not None:
        config["tags"] = tags
    if metadata is not None:
        config["metadata"] = metadata
    # Fast path for a retry after the original response was lost.
    snap = graph.get_state(config)
    if snap.next != ("review",):
        return _replay_completed(snap, request_id, payload_hash)
    with _exclusive_resume(graph):
        # Another process may have completed the review after the fast-path read.
        snap = graph.get_state(config)
        if snap.next != ("review",):
            return _replay_completed(snap, request_id, payload_hash)
        occurred_at = datetime.now(timezone.utc).isoformat()
        decision = {
            "event_id": str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"geha-review:{thread}:{request_id}")
            ),
            "thread_id": str(thread),
            "request_id": request_id,
            "payload_hash": payload_hash,
            "occurred_at": occurred_at,
            "actor_id": identity.subject,
            "actor_issuer": identity.issuer,
            "actor_roles": sorted(identity.roles),
            "action": action,
            "reason": reason,
            "edited_text": edited_text,
        }
        return graph.invoke(Command(resume=decision), config)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, default=ROOT.parent)
    p.add_argument("--db", type=Path, default=ROOT / "data/checkpoints.sqlite")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("example")
    start = sub.add_parser("start")
    start.add_argument("--claim")
    start.add_argument(
        "--actor", choices=["member", "outsider", "demo_operator"], default="member"
    )
    rev = sub.add_parser("review")
    rev.add_argument("thread")
    rev.add_argument("--action", choices=["approve", "reject"], required=True)
    rev.add_argument("--reason", required=True)
    rev.add_argument("--edit", help="Optional reviewer-edited explanation")
    rev.add_argument(
        "--request-id", help="Stable ID to make a retried review idempotent"
    )
    for name in ["show", "history"]:
        sub.add_parser(name).add_argument("thread")
    args = p.parse_args()
    if args.command == "example":
        print(json.dumps({"claim_id": load_inputs(args.base)[3], "actor": "member"}))
        return
    with workflow(args.db, args.base) as g:
        if args.command == "start":
            thread = str(uuid.uuid4())
            cfg = {"configurable": {"thread_id": thread}}
            g.invoke(
                {
                    "claim_id": args.claim or load_inputs(args.base)[3],
                    "actor": args.actor,
                },
                cfg,
            )
        else:
            thread = args.thread
            cfg = {"configurable": {"thread_id": thread}}
        if args.command == "review":
            resume(
                g,
                thread,
                args.action,
                args.reason,
                edited_text=args.edit,
                request_id=args.request_id or str(uuid.uuid4()),
            )
        if args.command == "history":
            output = [
                {
                    "created_at": s.created_at,
                    "step": s.metadata.get("step"),
                    "next": s.next,
                    "state": s.values,
                }
                for s in reversed(list(g.get_state_history(cfg)))
            ]
        else:
            snap = g.get_state(cfg)
            output = {"thread_id": thread, "next": snap.next, "state": snap.values}
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
