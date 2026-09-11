from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import UserContext


class AccessDeniedError(Exception):
    pass


class ClaimRepository:
    def __init__(self, claims_path: Path):
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        self._claims = {claim["claim_id"].upper(): claim for claim in claims}

    def get_authorized(self, claim_id: str, context: UserContext) -> dict[str, Any]:
        normalized = claim_id.upper()
        claim = self._claims.get(normalized)
        if claim is None:
            raise KeyError("Claim was not found")

        member_id = claim.get("member_id") or claim.get("insured_id")
        member_access = (
            context.role == "member" and member_id in context.subject_member_ids
        )
        staff_access = (
            context.role in {"adjuster", "clinical_reviewer", "compliance"}
            and normalized in context.authorized_claim_ids
        )

        if not (member_access or staff_access):
            raise AccessDeniedError("Claim was not found or is not authorized")
        return claim

