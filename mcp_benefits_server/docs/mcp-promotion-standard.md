# MCP promotion standard (v1)

How an MCP tool moves from an experiment to something production agents may call.
This demo enforces every rule below in code: `src/registry.py` holds the criteria,
`src/server.py` exposes only the tiers a deployment allows, and
`src/check_promotion.py` fails CI when a tool claims a tier it doesn't meet.

## 1. Tiers and deployments

| Tier | Who connects | Data allowed | Exposed in deployments |
|---|---|---|---|
| **sandbox** | developers, test agents | synthetic or public only | sandbox |
| **pilot** | named pilot users and agents | real, non-PHI (PHI only with all PHI controls) | sandbox, pilot |
| **production** | member- and staff-facing agents | public or internal, read-only | sandbox, pilot, production |

Tiers belong to *tools*; environments belong to *deployments*. An agent connects to
one deployment and sees only the tools promoted to that deployment's tier. A tool it
can't see is a tool the model can't call, even by mistake.

## 2. Promotion criteria

**Every tier**
- A named owner and a semantic version.
- A description of at least 40 characters: the model chooses tools by reading it.
- One of the approved patterns (section 3).
- Write tools require human approval before they act.
- PHI arguments are hashed in the audit log (`audit_hashing`).

**Pilot adds**
- Tests that exist and pass.
- PHI tools need all PHI controls: `audit_hashing`, `minimum_necessary`,
  `encryption_at_rest`, `hipaa_review`.

**Production adds**
- Evaluation evidence: results on a fixed question set, not just unit tests.
- Read-only access. Write tools stay at pilot in v1.
- No PHI. PHI tools stay at pilot in v1 until an enterprise PHI pattern is approved.

## 3. Approved patterns

| Pattern | Rule |
|---|---|
| `deterministic-lookup` | Read-only lookup over an authoritative table; no model output. |
| `document-search-with-citations` | Search over an approved corpus; every result cites its source. |
| `minimum-necessary-phi-read` | Aggregates for one member; never names, birth dates or free text. |
| `write-with-human-approval` | Proposes a change; executes only after explicit human confirmation. |

A tool that fits no pattern is a proposal for a new pattern, reviewed by architecture,
security and compliance before any tool may use it.

## 4. Runtime controls (all tiers)

- **Audit:** every call logs time, deployment, tool, version, tier, data class,
  arguments (PHI hashed), outcome and latency. Results are not logged.
- **Annotations:** tools publish MCP hints (`readOnlyHint`, `destructiveHint`,
  `idempotentHint`) so clients can require confirmation for writes.
- **Metadata:** tools publish tier, data class, access, pattern, owner and version, so
  gateways and clients can apply policy without reading code.

## 5. Lifecycle

1. **Propose:** a tool enters at sandbox with an owner and a pattern.
2. **Promote:** raise the tier in the registry in a pull request; CI runs
   `check_promotion.py`, which fails if a criterion is unmet. A reviewer from the
   owning team approves; PHI or write tools also need security and compliance approval.
3. **Change:** a breaking change to arguments or results is a new MAJOR version, and
   promotion starts again at pilot. Additive changes are MINOR.
4. **Retire:** mark deprecated for one release, then remove; the audit log shows
   which agents still call it.
5. **Re-review:** production tools are re-reviewed every six months, or whenever their
   source data changes (e.g. a new plan year).

## 6. Current tools (see `python check_promotion.py --report`)

| Tool | Tier | Blocks next tier |
|---|---|---|
| `rate_code_lookup`, `premium_quote`, `cdt_procedure_class` | production | none |
| `coverage_policy_search` | pilot | evaluation evidence (a gold-question retrieval benchmark) |
| `member_claims_summary` | sandbox | encryption at rest, HIPAA review |
| `submit_enrollment_change` | sandbox | eligible for pilot; never production in v1 |
