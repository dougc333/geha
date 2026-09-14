"""Synthetic 35-category classification task for the GEHA reference agent.

This defines a *labelled text -> category* task used to demonstrate a
self-improving training loop and its overfitting failure mode. All categories
are drawn from the health-payer/claims domain. Every category carries a set of
distinctive keyword signals so a keyword-weighted classifier can learn it, plus
a set of confusable "near-miss" terms shared with neighbours (so the task is
*not* trivially separable and misclassification is possible).

This is a synthetic benchmark, not production logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategorySpec:
    name: str
    keywords: tuple[str, ...]
    # "high_impact" categories are the positives for the false-positive metric.
    high_impact: bool = False


# 35 categories, ordered. `keywords` are the distinctive signal words used by
# the generator; the shared confuser pool is injected to keep the task hard.
CATEGORIES: list[CategorySpec] = [
    CategorySpec(
        "claim_submission", ("file", "submit", "submission", "837", "bill"), False
    ),
    CategorySpec(
        "claim_status", ("status", "track", "progress", "where", "check on"), False
    ),
    CategorySpec(
        "eligibility",
        ("eligible", "eligibility", "qualify", "enrolled", "covered"),
        False,
    ),
    CategorySpec(
        "benefits_plan",
        ("plan", "benefit", "option", "coverage level", "standard"),
        False,
    ),
    CategorySpec(
        "prior_authorization",
        ("prior auth", "precert", "authorization", "approval needed"),
        False,
    ),
    CategorySpec(
        "appeal", ("appeal", "reconsider", "dispute", "overturn", "contest"), True
    ),
    CategorySpec(
        "claim_denial", ("denied", "denial", "rejected", "not payable", "refused"), True
    ),
    CategorySpec(
        "premium_payment",
        ("premium", "pay bill", "due date", "installment", "overdue"),
        False,
    ),
    CategorySpec(
        "deductible", ("deductible", "out of pocket", "threshold", "met"), False
    ),
    CategorySpec(
        "coinsurance", ("coinsurance", "coinsurance rate", "percentage", "split"), False
    ),
    CategorySpec(
        "copay", ("copay", "copayment", "fixed amount", "office visit fee"), False
    ),
    CategorySpec(
        "out_of_network",
        ("out of network", "non-network", "balance bill", "oop max"),
        True,
    ),
    CategorySpec(
        "in_network",
        ("in network", "network provider", "contracted", "preferred"),
        False,
    ),
    CategorySpec(
        "provider_directory",
        ("directory", "find provider", "search doctor", "network lookup"),
        False,
    ),
    CategorySpec("cpt_code", ("cpt", "procedure code", "hcpcs", "billing code"), False),
    CategorySpec(
        "diagnosis_code", ("diagnosis", "icd", "icd-10", "diagnostic code"), False
    ),
    CategorySpec(
        "medical_necessity",
        ("medical necessity", "medically necessary", "needed", "appropriate care"),
        True,
    ),
    CategorySpec(
        "referral", ("referral", "specialist", "authorized doctor", "refer"), False
    ),
    CategorySpec(
        "telehealth",
        ("telehealth", "telemedicine", "virtual visit", "remote care"),
        False,
    ),
    CategorySpec(
        "prescription", ("prescription", "pharmacy", "drug", "medication", "rx"), False
    ),
    CategorySpec(
        "formulary", ("formulary", "tier", "covered drug", "drug list"), False
    ),
    CategorySpec("dental", ("dental", "dentist", "tooth", "oral"), False),
    CategorySpec(
        "vision", ("vision", "eye", "glasses", "optometrist", "contact lens"), False
    ),
    CategorySpec(
        "maternity", ("maternity", "pregnancy", "delivery", "prenatal"), False
    ),
    CategorySpec(
        "mental_health",
        ("mental health", "behavioral", "therapy", "counseling", "psych"),
        False,
    ),
    CategorySpec(
        "wellness",
        ("wellness", "preventive", "screening", "annual checkup", "physical"),
        False,
    ),
    CategorySpec(
        "claim_form", ("cms-1500", "form", "ubb", "ub-04", "paper claim"), False
    ),
    CategorySpec(
        "eob", ("eob", "explanation of benefits", "statement", "remittance"), False
    ),
    CategorySpec(
        "payment_plan",
        ("payment plan", "installments", "monthly payments", "budget"),
        False,
    ),
    CategorySpec(
        "hsa_fsa", ("hsa", "fsa", "health savings", "flexible spending"), False
    ),
    CategorySpec(
        "coordination_benefits",
        ("cob", "coordination", "secondary payer", "medicare primary"),
        False,
    ),
    CategorySpec(
        "fraud", ("fraud", "abuse", "waste", "suspicious claim", "identity theft"), True
    ),
    CategorySpec(
        "privacy_hipaa",
        ("hipaa", "privacy", "phi", "confidential", "protected health"),
        False,
    ),
    CategorySpec(
        "appeal_deadline",
        ("deadline", "within days", "timely", "submit by", "timeframe"),
        True,
    ),
    CategorySpec(
        "id_card",
        (
            "id card",
            "member id",
            "card number",
            "replacement card",
            "proof of coverage",
        ),
        False,
    ),
]


# Shared "confuser" terms injected into *all* examples so no single token is a
# perfect classifier. Keeps the benchmark non-trivial.
CONFUSER_POOL = (
    "insurance",
    "medical",
    "health",
    "my",
    "the",
    "please",
    "need",
    "about",
    "regarding",
    "claim",
    "benefit",
    "coverage",
    "member",
    "information",
)


def category_names() -> list[str]:
    return [c.name for c in CATEGORIES]


def spec_by_name(name: str) -> CategorySpec:
    for c in CATEGORIES:
        if c.name == name:
            return c
    raise KeyError(name)
