from __future__ import annotations

import re

from .models import AgentResponse, Citation, UserContext
from .repository import AccessDeniedError
from .tools import ReferenceTools


CLAIM_ID_RE = re.compile(r"\bCLM-\d+\b", re.IGNORECASE)


class ReferenceAgent:
    """A constrained orchestrator over approved reference tools.

    It provides administrative decision support. It never issues coverage,
    payment, fraud, or medical-necessity determinations.
    """

    HIGH_IMPACT_TERMS = {
        "approve",
        "deny",
        "denial",
        "covered",
        "coverage",
        "medical necessity",
        "fraud",
        "payment amount",
    }

    def __init__(self, tools: ReferenceTools):
        self.tools = tools

    def run(self, message: str, context: UserContext) -> AgentResponse:
        normalized = message.lower()
        claim_match = CLAIM_ID_RE.search(message)
        claim_id = claim_match.group(0).upper() if claim_match else None

        if any(term in normalized for term in ("appeal", "reconsider", "dispute")):
            return self._appeal(message, context, claim_id)
        if claim_id or ("claim" in normalized and "status" in normalized):
            return self._claim_status(context, claim_id)
        if any(
            term in normalized for term in ("prior auth", "precert", "authorization")
        ):
            return self._reference_query(message, context, "prior_authorization")
        if "claim" in normalized and any(
            term in normalized for term in ("file", "submit", "submission")
        ):
            return self._reference_query(message, context, "claim_submission")
        return self._reference_query(message, context, None)

    def _claim_status(
        self,
        context: UserContext,
        claim_id: str | None,
    ) -> AgentResponse:
        if not claim_id:
            return AgentResponse(
                intent="claim_status",
                answer="Provide the claim ID to retrieve an authorized claim status.",
            )
        try:
            summary, audit_id = self.tools.get_claim_summary(claim_id, context)
        except (KeyError, AccessDeniedError):
            return AgentResponse(
                intent="claim_status",
                answer="The claim was not found or you are not authorized to view it.",
            )

        answer = (
            f"Claim {summary['claim_id']} has simulated status "
            f"{summary['status']}. It was received on "
            f"{summary['received_date']} with a total submitted charge of "
            f"${summary['total_charge']:.2f}."
        )
        flags = summary.get("data_quality_flags", [])
        if flags:
            answer += (
                " The source record has data-quality flags: "
                + ", ".join(flags)
                + ". Verify it in the system of record."
            )
        return AgentResponse(
            intent="claim_status",
            answer=answer,
            needs_human_review=bool(flags),
            review_reason=(
                "The structured claim contains chronology or amount inconsistencies."
                if flags
                else None
            ),
            audit_id=audit_id,
            structured_data=summary,
        )

    def _appeal(
        self,
        message: str,
        context: UserContext,
        claim_id: str | None,
    ) -> AgentResponse:
        try:
            checklist, citations, audit_id = self.tools.build_appeal_checklist(
                context,
                claim_id,
            )
        except (KeyError, AccessDeniedError):
            return AgentResponse(
                intent="appeal_support",
                answer="The claim was not found or you are not authorized to view it.",
                needs_human_review=True,
                review_reason="Appeal support requires an authorized claim record.",
            )

        answer = (
            "Prepare the member and claim identifiers, provider and service "
            "details, a description of the dispute, supporting records, and "
            "the plan provision believed to apply. Submit the initial appeal "
            "through an official GEHA channel. A qualified appeals reviewer "
            "must validate deadlines, evidence, and the final determination."
        )
        return AgentResponse(
            intent="appeal_support",
            answer=answer,
            citations=self._dedupe_citations(citations),
            needs_human_review=True,
            review_reason="Appeals and disputed-claim outcomes are high-impact decisions.",
            audit_id=audit_id,
            structured_data=checklist,
        )

    def _reference_query(
        self,
        message: str,
        context: UserContext,
        topic: str | None,
    ) -> AgentResponse:
        results, audit_id = self.tools.search_public_reference(
            message,
            context,
            topic=topic,
        )
        if not results:
            return AgentResponse(
                intent=topic or "general_reference",
                answer=(
                    "The approved reference corpus does not contain enough "
                    "evidence to answer. Route the question to an authorized reviewer."
                ),
                needs_human_review=True,
                review_reason="Insufficient approved evidence.",
                audit_id=audit_id,
            )

        evidence = " ".join(result["text"] for result in results[:2])
        needs_review = any(term in message.lower() for term in self.HIGH_IMPACT_TERMS)
        return AgentResponse(
            intent=topic or "general_reference",
            answer=evidence,
            citations=self._dedupe_citations(
                [result["citation"] for result in results]
            ),
            needs_human_review=needs_review,
            review_reason=(
                "A qualified reviewer must make coverage, payment, fraud, or "
                "medical-necessity decisions."
                if needs_review
                else None
            ),
            audit_id=audit_id,
        )

    @staticmethod
    def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
        seen: set[tuple[str, str]] = set()
        output = []
        for citation in citations:
            key = (citation.title, citation.url)
            if key not in seen:
                seen.add(key)
                output.append(citation)
        return output
