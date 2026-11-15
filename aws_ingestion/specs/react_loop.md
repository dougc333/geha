# Spec: ReAct verification loop

Review status: DRAFT.

## Tools

| Tool | Input | Output |
|---|---|---|
| `render` | html | png at page aspect ratio (Playwright) |
| `diff_regions` | source png, html png | ranked mismatch regions with crops |
| `text_diff` | reference text, html text | word adds, drops, substitutions |
| `numeric_check` | reference text, html text | missing and extra numeric tokens |
| `crop` | bbox | zoomed region of the source page |
| `patch` | ops | JSON Patch on spec (pipeline 2) or HTML edit (pipeline 1) |

## Error count

`errors = missing_words + extra_words + numeric_mismatches + table_shape_mismatches + flagged_regions`

Lower is better. Recorded each iteration in `run.json`.

## Stop conditions (first to fire wins)

1. `errors == 0` -> `stop_reason: "clean"`.
2. iteration == 5 -> `stop_reason: "max_iterations"`.
3. No decrease in `errors` for 2 consecutive iterations -> `stop_reason: "plateau"`.
4. A patch makes `errors` worse by more than 20% -> revert it, count as no improvement.

## Rules

- The agent MUST NOT invent text or numbers not visible in the source page.
- Values read only from a chart, not printed, MUST be omitted and noted, not estimated.
- Every patch is logged with iteration number and rationale for audit.
- Scanned pages have no text ground truth: the vision judge's flagged regions are the only error signal, so the page stays `low_confidence`.
