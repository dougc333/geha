"""Default policies for the repo's tool-calling agents, from the tools each one actually binds.

Common shape: the reads an agent is built around are ALLOW, writes are ASK, shell/code
execution is ASK (script inspection runs on top), and anything else falls to the default
ASK, which a non-interactive run (server, ladder, test) turns into DENY. So a tool that
shows up unexpectedly (a new MCP tool, a renamed one) is blocked until a rule names it.
"""

from __future__ import annotations

from .policy import ALLOW, ASK, DENY, Policy, Rule

FHIR_READS = [
    Rule("fhir_search", ALLOW, "FHIR read"),
    Rule("fhir_read", ALLOW, "FHIR read"),
]
FHIR_WRITES = [
    Rule("re:^fhir_(create|update|patch|delete|transaction|batch|conditional_\\w+)$", ASK,
         "FHIR write: changes server data"),
]
EXECUTION = [
    # Shell / code-execution tools (e.g. ShellToolMiddleware's "shell"): never silently.
    Rule("re:^(shell|bash|terminal|run_command|execute|python_repl|code_interpreter)$", ASK,
         "runs commands or code"),
]
SECRETS = [
    Rule("*", DENY, "argument points at secrets", args={"path": "re:(^|/)(\\.env|\\.ssh|id_rsa)"}),
]
ANALYTIC_TOOLS = ["provider_billing_summary", "top_services", "service_cost_by_provider",
                  "find_duplicate_claims", "claims_after_patient_death", "provider_daily_load"]


def fhir_agent_policy() -> Policy:
    """hapi/langgraph_agent.py (pharmacy_agent.py reuses its graph with pharmacy_policy)."""
    return Policy([*SECRETS, *FHIR_READS, *FHIR_WRITES, *EXECUTION], default=ASK)


RXNORM_READS = ["rxnorm_search", "rxnorm_get_properties", "rxnorm_related", "rxnorm_ndc"]
OPENFDA_READS = ["openfda_drug_profile", "openfda_search_recalls", "openfda_search_drug_shortages",
                 "openfda_get_drug_label", "openfda_lookup_ndc"]


def pharmacy_policy() -> Policy:
    """hapi/pharmacy_agent.py: FHIR reads plus the public RxNorm / openFDA look-ups it binds."""
    return Policy([*SECRETS, *FHIR_READS,
                   *[Rule(name, ALLOW, "public drug look-up") for name in RXNORM_READS + OPENFDA_READS],
                   *FHIR_WRITES, *EXECUTION], default=ASK)


def fraud_policy(extra_allow: list[str] = ()) -> Policy:
    """hapi/fraud/agent.py: FHIR reads plus the read-only claims analytics.
    `extra_allow`: tool names the caller vouches for (the self-improving agent's learned
    tools, which a person approved in learned.py)."""
    return Policy([*SECRETS, *FHIR_READS,
                   *[Rule(name, ALLOW, "claims analytics (read-only aggregate)") for name in ANALYTIC_TOOLS],
                   *[Rule(name, ALLOW, "learned tool (approved in learned.py)") for name in extra_allow],
                   *FHIR_WRITES, *EXECUTION], default=ASK)


def self_improving_policy(learned_tools: list[str] = ()) -> Policy:
    """hapi/self-improving-agents/agent.py: the fraud policy plus the learned tools loaded
    for this run (only statuses the caller asked for, normally "approved")."""
    return fraud_policy(list(learned_tools))


DECLINED = "The member declined; nothing was submitted."


def benefits_policy() -> Policy:
    """mcp_benefits_server/agent/benefits_agent.py. Reads (public and, in sandbox, synthetic
    PHI) are allowed: the server's MCP_ENV already decides which exist and audits PHI calls.
    submit_enrollment_change with confirm=true needs the member's approval; without
    confirm it is only a preview, which the server refuses to act on."""
    return Policy([
        Rule("submit_enrollment_change", ASK, "submits an enrollment change", args={"confirm": True},
             message=DECLINED),
        Rule("submit_enrollment_change", ALLOW, "preview only (confirm is not true)"),
        Rule("rate_code_lookup", ALLOW, "public read"),
        Rule("premium_quote", ALLOW, "public read"),
        Rule("cdt_procedure_class", ALLOW, "public read"),
        Rule("coverage_policy_search", ALLOW, "public read (pilot)"),
        Rule("member_claims_summary", ALLOW, "PHI read (sandbox, synthetic; audited by the server)"),
        *EXECUTION,
    ], default=ASK)
