"""Context compiler vs plain agent on the same coding session.

All agents share one append-only event log. Before each model call:
  plain        sends every event in full (the usual chat history)
  compiler v1  re-scores every event against the current query and renders it as
               hide | short | long | full
  compiler v2  sends each new event in full once, then scores it once and freezes
               that level, so older blocks never change and the cache prefix holds

The session is scripted: one "episode" is a 10-event debugging task (failing test
-> read files -> fix -> follow-up request) with 8 model calls. --episodes N runs N
of them back to back in one session (each on its own module), so the history keeps
growing. Runs offline with no API key. For each call it records input tokens,
prompt-cache hits, dollar cost and recall: whether the facts that call needs are
still in the context.

Run:  python context_compiler/demo.py                  # one episode, per-call tables
      python context_compiler/demo.py --episodes 20 --plot context_compiler/cost.png
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

# Sonnet prices in $ per million tokens. Every call caches its whole prompt, so
# tokens matching the previous call's prefix are cache reads and the rest are
# cache writes (1.25x input).
PRICE = {"cache_read": 0.30, "cache_write": 3.75, "output": 15.00}
# Assumed cost of scoring one event (~100-token Haiku call). Jev does not
# expose its price; set this from your TypeSafe pricing.
SCORER_COST_PER_EVENT = 0.0001
OUTPUT_TOKENS_PER_CALL = 300
CONTEXT_LIMIT = 200_000

SYSTEM = "You are a coding agent. Tools: read, bash, edit, write. Think, then call one tool."


def tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class Event:
    id: int
    kind: str      # user | assistant | tool_result
    text: str      # full payload
    short: str     # one-line summary, written when the event is appended
    long: str      # key lines, written when the event is appended


def filler(make_line, n: int) -> str:
    return "\n".join(make_line(i) for i in range(n))


# ---------------------------------------------------------------- scenario --

def episode(k: int) -> tuple[list[Event], list[tuple[int, list[str]]]]:
    """One debugging task on module ``billing/pricing_k.py``: 10 events, 8 calls."""
    test, mod, fn = f"test_member_discount_{k}", f"billing/pricing_{k}.py", f"checkout_{k}"
    bad, good, passed = f"{81 + k}.0", f"{90 + k}.0", f"{213 + k} passed"
    pytest_fail = (
        filler(lambda i: f"tests/test_module_{i}.py ....................  [{i}%]", 200)
        + f"\n_________________ {test} _________________\n"
        + f">       assert {fn}(cart(100), member=True, coupon=None) == {good}\n"
        + f"E       assert {bad} == {good}\nFAILED tests/test_billing.py::{test}\n1 failed, {212 + k} passed")
    pricing = (
        filler(lambda i: f"def price_rule_{i}(cart): return cart.total * {1 + i / 1000:.3f}  # regional rule", 150)
        + "\ndef apply_member_discount(price): return price * 0.9\n"
        + f"def {fn}(cart, member, coupon):\n    price = cart.total\n"
        + "    if member: price = apply_member_discount(price)\n"
        + "    if coupon or member: price = apply_member_discount(price)  # coupon path\n    return price\n"
        + filler(lambda i: f"def tax_rule_{i}(price): return price * 1.0{i % 10}  # state tax table", 150))
    logging = filler(lambda i: f"def log_{i}(msg): return _emit('channel_{i}', msg, level={i % 5})", 300)
    grep = (filler(lambda i: f"tests/fixtures/orders_{i}.json:  \"apply_member_discount\": false", 40)
            + f"\n{mod}:153:    if coupon or member: price = apply_member_discount(price)  # coupon path")
    pytest_pass = filler(lambda i: f"tests/test_module_{i}.py ....................  [{i}%]", 200) + f"\n{passed}"
    changelog = f"# Changelog\n## Unreleased ({mod})\n- nothing yet\n" + filler(
        lambda i: f"## 2.{40 - i // 10}.{i % 10}\n- maintenance release {i}", 250)
    root = f"Root cause: the member discount is applied twice in {fn}() via the coupon path ({mod}:153)."

    rows = [
        ("user", f"The test {test} in tests/test_billing.py is failing. Fix it.",
         f"User: fix failing {test}.", f"User: fix failing {test}."),
        ("tool_result", pytest_fail, f"pytest: 1 failed ({test}).",
         f"pytest: {test} FAILED: assert {bad} == {good} for {fn}(cart(100), member=True)."),
        ("tool_result", pricing, f"read {mod}: price, tax and discount rules.",
         f"{mod}: def apply_member_discount(price): price * 0.9; def {fn}(cart, member, coupon) "
         f"applies apply_member_discount twice when member (coupon path)."),
        ("tool_result", logging, "read utils/logging.py: 300 log channel helpers.",
         "utils/logging.py: log_N(msg) helpers emitting to channels; nothing about billing."),
        ("tool_result", grep, "grep apply_member_discount: 41 hits, 40 in fixtures.",
         f"grep apply_member_discount: {mod}:153 coupon path calls it a second time."),
        ("assistant", root + " Removing the second call.", f"Root cause: discount applied twice in {fn}().",
         root + " Removing the second call."),
        ("tool_result", f"edit {mod}: line 153 now applies the coupon discount only.",
         f"edit {mod}:153 done.", f"edit {mod}: line 153 now applies coupon only."),
        ("tool_result", pytest_pass, f"pytest: {passed}.", f"pytest: {passed}, 0 failed."),
        ("user", f"Great. Now add a test that a coupon and the member discount stack correctly in {fn}, "
         "and add the fix to the CHANGELOG.",
         f"User: add coupon + member stacking test for {fn}; update CHANGELOG.",
         f"User: add coupon + member stacking test for {fn}; update CHANGELOG."),
        ("tool_result", changelog, "read CHANGELOG.md: Unreleased section is empty.",
         f"CHANGELOG.md: '## Unreleased ({mod})' section with '- nothing yet', then release history."),
    ]
    events = [Event(10 * k + j + 1, *row) for j, row in enumerate(rows)]
    sig = f"def {fn}(cart, member, coupon)"
    calls = [(1, [test]), (2, [f"{bad} == {good}"]), (3, ["coupon path", sig]), (5, [f"{mod}:153"]),
             (7, [f"edit {mod}"]), (8, [passed]), (9, [f"applied twice in {fn}", sig]),
             (10, [f"## Unreleased ({mod})", sig])]
    return events, calls


def session(n_episodes: int) -> tuple[list[Event], list[tuple[int, list[str]]]]:
    events, calls = [], []
    for k in range(n_episodes):
        ev, cl = episode(k)
        calls += [(len(events) + n, needed) for n, needed in cl]
        events += ev
    return events, calls


# ------------------------------------------------------------------ agents --

STOP = {"the", "and", "that", "with", "this", "from", "now", "add", "for", "are", "into", "nothing"}


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z_0-9]{4,}", text.lower()) if w not in STOP}


def score(event: Event, query: str, age: int) -> str:
    """Rules scorer standing in for Jev/Haiku: hide | short | long | full."""
    if event.kind == "user" or age < 2:
        return "full"                      # pinned: user requests and the last two events
    overlap = len(words(query) & words(event.long))
    if overlap >= 3 or event.kind == "assistant":
        return "long"
    if overlap >= 1:
        return "short"
    return "hide"


def render(event: Event, level: str) -> str | None:
    body = {"full": event.text, "long": event.long, "short": event.short, "hide": None}[level]
    return None if body is None else f"[{event.id} {event.kind} {level}]\n{body}"


def current_query(log: list[Event]) -> str:
    last_user = next(e for e in reversed(log) if e.kind == "user")
    return last_user.text + " " + log[-1].long


class Plain:
    name = "plain"

    def __call__(self, log):
        return [SYSTEM] + [render(e, "full") for e in log], {}, 0


class CompilerV1:
    """Re-scores every event on every call."""
    name = "compiler v1"

    def __call__(self, log):
        query = current_query(log)
        levels = {e.id: score(e, query, len(log) - 1 - i) for i, e in enumerate(log)}
        blocks = [render(e, levels[e.id]) for e in log]
        return [SYSTEM] + [b for b in blocks if b is not None], levels, len(log)


class CompilerV2:
    """Each new event is sent in full once, then scored once and frozen at that level.

    Older blocks never change, so the context grows only at the end and the
    cached prefix survives. The cost: a later query can't bring back detail
    from an event frozen at a low level.
    """
    name = "compiler v2"

    def __init__(self):
        self.frozen: dict[int, str] = {}
        self.seen = 0

    def __call__(self, log):
        query = current_query(log)
        levels, scored = {}, 0
        for i, e in enumerate(log):
            if i >= self.seen:
                levels[e.id] = "full"          # new since the last call
                continue
            if e.id not in self.frozen:
                self.frozen[e.id] = score(e, query, age=99)
                scored += 1
            levels[e.id] = self.frozen[e.id]
        self.seen = len(log)
        blocks = [render(e, levels[e.id]) for e in log]
        return [SYSTEM] + [b for b in blocks if b is not None], levels, scored


def cached_prefix_tokens(prev: list[str], cur: list[str]) -> int:
    n = 0
    for a, b in zip(prev, cur):
        if a != b:
            break
        n += tokens(a)
    return n


def run(agent, events, calls) -> dict:
    prev: list[str] = []
    out = {"name": agent.name, "rows": [], "input": 0, "cached": 0, "cost": 0.0, "hits": 0, "needed": 0}
    for n_events, needed in calls:
        blocks, levels, scored = agent(events[:n_events])
        text = "\n".join(blocks)
        inp = sum(tokens(b) for b in blocks)
        cached = cached_prefix_tokens(prev, blocks)
        cost = (cached * PRICE["cache_read"] + (inp - cached) * PRICE["cache_write"]
                + OUTPUT_TOKENS_PER_CALL * PRICE["output"]) / 1e6 + scored * SCORER_COST_PER_EVENT
        hits = sum(fact in text for fact in needed)
        out["input"] += inp
        out["cached"] += cached
        out["cost"] += cost
        out["hits"] += hits
        out["needed"] += len(needed)
        mix = " ".join(f"{lvl[0].upper()}{sum(v == lvl for v in levels.values())}"
                       for lvl in ("full", "long", "short", "hide")) if levels else "all full"
        out["rows"].append({"events": n_events, "input": inp, "cached": cached, "cost": cost,
                            "cum_cost": out["cost"], "recall": f"{hits}/{len(needed)}", "mix": mix})
        prev = blocks
    return out


def print_calls(r: dict) -> None:
    print(f"\n{r['name'].upper()}")
    print(f"{'events':>6} {'input tok':>10} {'cached':>8} {'cost $':>8} {'recall':>7}  levels (Full/Long/Short/Hide)")
    for row in r["rows"]:
        print(f"{row['events']:>6} {row['input']:>10,} {row['cached']:>8,} {row['cost']:>8.4f} "
              f"{row['recall']:>7}  {row['mix']}")


def crossover(a: dict, b: dict) -> int | None:
    """First call (1-based) after which b's cumulative cost stays below a's."""
    for i in range(len(a["rows"])):
        if all(rb["cum_cost"] < ra["cum_cost"] for ra, rb in zip(a["rows"][i:], b["rows"][i:])):
            return i + 1
    return None


def plot(results: list[dict], path: str, n_episodes: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"plain": "#2a78d6", "compiler v1": "#eb6834", "compiler v2": "#1baf7a"}  # categorical slots 1-3
    ink, muted, grid = "#1f1f1e", "#6b6a64", "#e6e5e0"
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for r in results:
        xs = range(1, len(r["rows"]) + 1)
        ys = [row["cum_cost"] for row in r["rows"]]
        ax.plot(xs, ys, color=colors[r["name"]], linewidth=2, solid_capstyle="round")
        recall = r["hits"] / r["needed"]
        ax.annotate(f"{r['name']}  ${ys[-1]:.2f} · recall {recall:.0%}", (xs[-1], ys[-1]),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=ink)

    plain = next(r for r in results if r["name"] == "plain")
    over = next((i for i, row in enumerate(plain["rows"], 1) if row["input"] > CONTEXT_LIMIT), None)
    if over:
        ax.axvline(over, color=muted, linewidth=1, linestyle=(0, (3, 3)))
        ax.annotate("plain history passes 200k tokens", (over, ax.get_ylim()[1] * 0.95),
                    xytext=(6, 0), textcoords="offset points", fontsize=8.5, color=muted, va="top")
    # Zoomed inset: the first calls, where the lines cross.
    zoom = 16
    inset = ax.inset_axes((0.06, 0.48, 0.36, 0.44))
    inset.set_facecolor("#fcfcfb")
    for r in results:
        rows = r["rows"][:zoom]
        inset.plot(range(1, len(rows) + 1), [row["cum_cost"] for row in rows],
                   color=colors[r["name"]], linewidth=2, marker="o", markersize=3)
        cross = crossover(plain, r) if r is not plain else None
        if cross and cross <= zoom:
            y = r["rows"][cross - 1]["cum_cost"]
            inset.plot([cross], [y], marker="o", markersize=8, color=colors[r["name"]],
                       markeredgecolor="#fcfcfb", markeredgewidth=2, zorder=5)
            inset.annotate(f"{r['name']} cheaper\nfrom call {cross}", (cross, y), xytext=(6, -22),
                           textcoords="offset points", fontsize=7.5, color=ink)
    inset.set_title(f"first {zoom} calls", fontsize=8.5, color=muted, loc="left")
    inset.grid(axis="y", color=grid, linewidth=0.6)
    inset.tick_params(colors=muted, labelsize=7, length=0)
    for side in ("top", "right"):
        inset.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        inset.spines[side].set_color(grid)

    ax.set_title(f"Cumulative cost over one growing session ({n_episodes} tasks, {len(plain['rows'])} model calls)",
                 loc="left", fontsize=11.5, color=ink, pad=12)
    ax.set_xlabel("model call", color=muted, fontsize=9.5)
    ax.set_ylabel("cumulative cost ($)", color=muted, fontsize=9.5)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.tick_params(colors=muted, labelsize=8.5, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.set_xlim(1, len(plain["rows"]) * 1.32)
    ax.set_ylim(bottom=0)
    fig.text(0.01, 0.01, f"Sonnet prices with prompt caching; scorer assumed ${SCORER_COST_PER_EVENT}/event; "
             f"{OUTPUT_TOKENS_PER_CALL} output tokens per call.", fontsize=7.5, color=muted)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=fig.get_facecolor())
    print(f"\nwrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episodes", type=int, default=1, help="debugging tasks run back to back in one session")
    parser.add_argument("--plot", help="write a cumulative-cost chart to this PNG path")
    args = parser.parse_args()

    events, calls = session(args.episodes)
    results = [run(agent, events, calls) for agent in (Plain(), CompilerV1(), CompilerV2())]
    if args.episodes == 1:
        for r in results:
            print_calls(r)

    print(f"\nTOTALS  ({args.episodes} tasks, {len(calls)} calls, {len(events)} events)")
    print(f"{'':12} {'input tok':>12} {'cache hit':>9} {'cost $':>8} {'recall':>9} {'last call tok':>14}")
    plain = results[0]
    for r in results:
        hit = r["cached"] / r["input"]
        print(f"{r['name']:12} {r['input']:>12,} {hit:>9.0%} {r['cost']:>8.3f} "
              f"{r['hits']:>4}/{r['needed']:<4} {r['rows'][-1]['input']:>14,}")
    for r in results[1:]:
        print(f"{r['name']} / plain: {r['input'] / plain['input']:.0%} of input tokens, "
              f"{r['cost'] / plain['cost']:.0%} of cost; cheaper from call {crossover(plain, r)}")
    if args.plot:
        plot(results, args.plot, args.episodes)


if __name__ == "__main__":
    main()
