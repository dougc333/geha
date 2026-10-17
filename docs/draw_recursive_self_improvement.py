"""Draw recursive self-improvement: a teacher model rewrites a student model's prompt in a loop.

    .venv/bin/python docs/draw_recursive_self_improvement.py
writes recursive_self_improvement.png and .svg next to this file.

The student's prompt is the benefits agent's real system prompt
(mcp_benefits_server/agent/benefits_agent.py) plus one rule a teacher could add after reading
failed transcripts - the "new starts only" qualifier the context-assembly evals showed models
guess at when the note is missing.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
INK, MUTED, LINE, SURFACE = "#1f1f1e", "#6b6a64", "#d9d8d2", "#fcfcfb"
TEACHER, TEACHER_TINT = "#4a3aa7", "#ece9f8"     # categorical violet
STUDENT, STUDENT_TINT = "#2a78d6", "#e7f0fb"     # categorical blue
DOWN, UP = "#eb6834", "#1baf7a"                  # arrow colours (orange, aqua)
NEW = "#fff3c4"                                  # the line the teacher added
MONO = "DejaVu Sans Mono"

PROMPT_BASE = [
    "You are a GEHA 2026 dental benefits assistant for federal members.",
    "Use the tools for every fact: rate codes, premiums, procedure classes and",
    "policy criteria come only from tool results, never from memory or your own",
    "arithmetic. Cite the source each tool returns. If no tool can answer, say",
    "so plainly. You never submit an enrollment change without the member's",
    "explicit approval.",
]
PROMPT_NEW = [
    "If a policy note limits a rule (\"new starts only\", a footnote, an exception),",
    "state that limit. If no note says, say it is not stated - do not guess.",
]

fig, ax = plt.subplots(figsize=(14, 10.5), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_xlim(0, 140)
ax.set_ylim(0, 105)
ax.axis("off")


def box(x, y, w, h, fc, ec, lw=1.6, r=2.0, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def curved(start, end, color, rad):
    ax.add_patch(FancyArrowPatch(start, end, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                                 mutation_scale=26, lw=3.2, color=color, zorder=1))


# --- title ---------------------------------------------------------------------------------
ax.text(70, 101, "Recursive self-improvement: a teacher model rewrites the student's prompt",
        ha="center", va="center", fontsize=17, weight="bold", color=INK)
ax.text(70, 97.4, "Each round the student runs on the eval set; the teacher reads its outputs and scores and "
        "proposes a better prompt. No weights change.", ha="center", va="center", fontsize=10.5, color=MUTED)

# --- teacher (top) ----------------------------------------------------------------------------
box(35, 74, 70, 18, TEACHER_TINT, TEACHER)
ax.text(70, 88.2, "Teacher model", ha="center", fontsize=16, weight="bold", color=TEACHER)
ax.text(70, 85.0, "larger model, e.g. Opus", ha="center", fontsize=10.5, color=MUTED)
for i, line in enumerate(["1. Read failed transcripts and scores",
                          "2. Diagnose why: missing rule, guessed fact, wrong tool",
                          "3. Rewrite the student's prompt (one change per round)"]):
    ax.text(41, 81.2 - i * 2.7, line, ha="left", va="center", fontsize=10.5, color=INK)

# --- student (bottom) with its prompt ----------------------------------------------------------
SX, SY, SW, SH = 22, 12, 96, 38
box(SX, SY, SW, SH, STUDENT_TINT, STUDENT)
ax.text(70, SY + SH - 4.2, "Student model", ha="center", fontsize=16, weight="bold", color=STUDENT)
ax.text(70, SY + SH - 7.4, "smaller, cheaper model that answers members, e.g. Sonnet or Haiku",
        ha="center", fontsize=10.5, color=MUTED)

PX, PW = SX + 3.5, SW - 7
lines = len(PROMPT_BASE) + len(PROMPT_NEW)
line_h, top = 2.05, SY + SH - 12.6
GAP = 2.6  # room for the 'added by teacher' label above the new rule
box(PX, top - lines * line_h - GAP - 4.0, PW, lines * line_h + GAP + 5.8, "white", LINE, lw=1.0, r=1.0, z=3)
ax.text(PX + 1.6, top + 0.2, "SYSTEM PROMPT  v3", ha="left", va="center", fontsize=8.6,
        family=MONO, color=MUTED, weight="bold", zorder=4)
y = top - 2.6
for line in PROMPT_BASE:
    ax.text(PX + 1.6, y, line, ha="left", va="center", fontsize=8.4, family=MONO, color=INK, zorder=4)
    y -= line_h
ax.text(PX + PW - 1.2, y - 0.2, "added by teacher in v3", ha="right", va="center", fontsize=7.8,
        color="#8a6d00", style="italic", zorder=4)
y -= GAP
box(PX + 0.8, y - len(PROMPT_NEW) * line_h + 1.0, PW - 1.6, len(PROMPT_NEW) * line_h + 0.4,
    NEW, "#e2c35a", lw=0.8, r=0.6, z=3.5)
for line in PROMPT_NEW:
    ax.text(PX + 1.6, y, line, ha="left", va="center", fontsize=8.4, family=MONO, color=INK, zorder=4)
    y -= line_h

# --- the loop -------------------------------------------------------------------------------------
curved((36, 76), (25, 50.5), DOWN, 0.35)   # teacher -> student, down the left
curved((115, 50.5), (104, 76), UP, 0.35)   # student -> teacher, up the right

ax.text(10, 66, "improved prompt\n(v n → v n+1)", ha="center", va="center", fontsize=11.5,
        weight="bold", color=DOWN, linespacing=1.3)
ax.text(10, 60.6, "rewrites instructions,\nadds rules and examples", ha="center", va="center",
        fontsize=9.5, color=MUTED, linespacing=1.3)
ax.text(130, 66, "outputs + scores", ha="center", va="center", fontsize=11.5, weight="bold", color=UP)
ax.text(130, 60.0, "answers and transcripts\non the eval set,\npass/fail per case", ha="center",
        va="center", fontsize=9.5, color=MUTED, linespacing=1.3)

# keep-or-revert gate in the middle of the loop
box(52, 54.5, 36, 13.5, "white", INK, lw=1.2, r=1.2, z=3)
ax.text(70, 64.9, "Keep the new prompt only if", ha="center", fontsize=10, weight="bold", color=INK, zorder=4)
ax.text(70, 62.0, "the held-out test score improves", ha="center", fontsize=10, color=INK, zorder=4)
ax.text(70, 59.4, "by more than the noise; else revert", ha="center", fontsize=10, color=INK, zorder=4)
ax.text(70, 56.6, "(teacher reads train failures only)", ha="center", fontsize=8.6, color=MUTED, zorder=4)

ax.text(70, 8.3, "Loop until the score stops improving or the budget runs out.", ha="center",
        fontsize=9.5, color=MUTED)

for ext in ("png", "svg"):
    fig.savefig(HERE / f"recursive_self_improvement.{ext}", facecolor=SURFACE, bbox_inches="tight")
print("wrote docs/recursive_self_improvement.png and .svg")
