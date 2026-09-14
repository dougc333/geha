from __future__ import annotations

from datetime import datetime
from typing import Any

from .audit import AuditLogger
from .models import Citation, UserContext
from .repository import AccessDeniedError, ClaimRepository
from .retrieval import InMemoryVectorIndex


class ReferenceTools:
    def __init__(
        self,
        claims: ClaimRepository,
        knowledge: InMemoryVectorIndex,
        audit: AuditLogger,
    ):
        self.claims = claims
        self.knowledge = knowledge
        self.audit = audit

    def search_public_reference(
        self,
        query: str,
        context: UserContext,
        *,
        topic: str | None = None,
        limit: int = 4,
    ) -> tuple[list[dict[str, Any]], str]:
        metadata_filter = {"topic": topic} if topic else None
        results = self.knowledge.search(
            query,
            limit=limit,
            metadata_filter=metadata_filter,
        )
        audit_id = self.audit.record(
            actor_id=context.actor_id,
            role=context.role,
            action="search_public_reference",
            outcome="success",
        )
        return [
            {
                "score": score,
                "text": chunk.text,
                "citation": chunk.citation,
                "metadata": chunk.metadata,
            }
            for score, chunk in results
        ], audit_id

    def get_claim_summary(
        self,
        claim_id: str,
        context: UserContext,
    ) -> tuple[dict[str, Any], str]:
        try:
            claim = self.claims.get_authorized(claim_id, context)
        except (KeyError, AccessDeniedError):
            self.audit.record(
                actor_id=context.actor_id,
                role=context.role,
                action="get_claim_summary",
                resource_ids=(claim_id.upper(),),
                outcome="denied",
            )
            raise

        safe_summary = {
            "claim_id": claim["claim_id"],
            "plan": claim.get("plan"),
            "status": claim.get("status"),
            "submitted_date": claim.get("submitted_date"),
            "received_date": claim.get("received_date"),
            "total_charge": claim.get("total_charge"),
            "diagnosis_code": claim.get("diagnosis", {}).get("code"),
            "service_codes": [
                line.get("cpt") for line in claim.get("service_lines", [])
            ],
        }
        safe_summary["data_quality_flags"] = self._claim_quality_flags(claim)
        audit_id = self.audit.record(
            actor_id=context.actor_id,
            role=context.role,
            action="get_claim_summary",
            resource_ids=(claim_id.upper(),),
            outcome="success",
        )
        return safe_summary, audit_id

    @staticmethod
    def _claim_quality_flags(claim: dict[str, Any]) -> list[str]:
        flags: list[str] = []

        def parse(value: str | None) -> datetime | None:
            if not value:
                return None
            for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, pattern)
                except ValueError:
                    continue
            flags.append(f"unparseable_date:{value}")
            return None

        submitted = parse(claim.get("submitted_date"))
        received = parse(claim.get("received_date"))
        service_dates = [
            parsed
            for line in claim.get("service_lines", [])
            if (parsed := parse(line.get("from_date"))) is not None
        ]
        latest_service = max(service_dates) if service_dates else None

        if submitted and received and received < submitted:
            flags.append("received_before_submitted")
        if latest_service and submitted and submitted < latest_service:
            flags.append("submitted_before_service")
        if latest_service and received and received < latest_service:
            flags.append("received_before_service")

        line_total = round(
            sum(
                float(line.get("charge") or 0)
                for line in claim.get("service_lines", [])
            ),
            2,
        )
        claim_total = round(float(claim.get("total_charge") or 0), 2)
        if line_total != claim_total:
            flags.append("service_line_total_mismatch")
        return flags

    def build_appeal_checklist(
        self,
        context: UserContext,
        claim_id: str | None = None,
    ) -> tuple[dict[str, Any], list[Citation], str]:
        claim_summary = None
        if claim_id:
            claim_summary, _ = self.get_claim_summary(claim_id, context)

        results, audit_id = self.search_public_reference(
            "appeal denied claim reconsideration required information deadline OPM",
            context,
            topic="appeals",
            limit=3,
        )
        checklist = {
            "claim": claim_summary,
            "required_fields": [
                "member name and member ID",
                "date of birth and plan name",
                "date of service and claim control number",
                "total billed amount and provider name",
                "description of the dispute",
                "supporting records and the relevant plan provision",
            ],
            "workflow": [
                "initial appeal to GEHA",
                "GEHA reconsideration if the decision is upheld",
                "OPM review when applicable after internal review",
            ],
        }
        citations = [result["citation"] for result in results]
        return checklist, citations, audit_id
