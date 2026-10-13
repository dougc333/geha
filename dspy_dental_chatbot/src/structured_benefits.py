"""Deterministic extraction and lookup for the dental benefit comparison table."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceRef:
    document_id: str
    plan_year: int
    page: int
    section: str


@dataclass(frozen=True)
class BenefitRecord:
    benefit_class: str
    benefit_name: str
    description: str
    high_cost: str
    standard_in_network_cost: str
    standard_out_of_network_cost: str
    source: SourceRef


@dataclass(frozen=True)
class ResolvedBenefit:
    code: str
    service: str
    record: BenefitRecord

    def evidence_text(self) -> str:
        """Serialize one resolved row so the LLM never has to align table columns."""
        payload = {
            "evidence_type": "deterministic_benefit_lookup",
            "code": self.code,
            "service": self.service,
            "benefit_class": self.record.benefit_class,
            "benefit_description": self.record.description,
            "high_cost": self.record.high_cost,
            "standard_in_network_cost": self.record.standard_in_network_cost,
            "standard_out_of_network_cost": self.record.standard_out_of_network_cost,
            "source": asdict(self.record.source),
        }
        return "STRUCTURED BENEFIT RECORD\n" + json.dumps(payload, indent=2)


CODE_RULES = {
    "D1110": {"benefit_class": "Class A", "service": "Adult prophylaxis / cleaning", "term": "cleanings"},
    "D7140": {"benefit_class": "Class B", "service": "Simple extraction", "term": "extractions"},
    "D3310": {"benefit_class": "Class C", "service": "Anterior root canal", "term": "root canals"},
}


def _clean_cell(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "; ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def parse_benefit_table(markdown: str, source: SourceRef) -> list[BenefitRecord]:
    """Parse the five-column benefits Markdown table into typed records."""
    rows = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("| 2026 dental benefit"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r"-+", cell) for cell in cells):
            continue
        if len(cells) != 5:
            continue
        class_match = re.search(r"Class\s+([A-D])", cells[0], flags=re.IGNORECASE)
        if not class_match:
            continue
        benefit_class = f"Class {class_match.group(1).upper()}"
        rows.append(
            BenefitRecord(
                benefit_class=benefit_class,
                benefit_name=cells[0],
                description=cells[1],
                high_cost=cells[2],
                standard_in_network_cost=cells[3],
                standard_out_of_network_cost=cells[4],
                source=source,
            )
        )
    if not rows:
        raise ValueError("No benefit rows found in comparison table")
    return rows


class StructuredBenefitIndex:
    def __init__(self, records: list[BenefitRecord]):
        self.records = records

    @classmethod
    def from_markdown(cls, path: str | Path) -> "StructuredBenefitIndex":
        path = Path(path)
        year_match = re.search(r"(20\d{2})", path.as_posix())
        page_label = path.parent.name if path.name == "page.md" else path.stem
        page_match = re.search(r"page-(\d+)$", page_label)
        if not page_match:
            raise ValueError(f"Cannot determine source page from {path}")
        source = SourceRef(
            document_id="geha-dental-benefits-guide",
            plan_year=int(year_match.group(1)) if year_match else 0,
            page=int(page_match.group(1)),
            section="Dental benefit comparison",
        )
        try:
            return cls(parse_benefit_table(path.read_text(), source))
        except ValueError:
            # Canonical crawl runs keep normalized table rows as JSON rather
            # than embedding a Markdown table in page.md.
            artifact_root = path.parents[2]
            table_dir = (
                artifact_root / "tables"
                if (artifact_root / "tables").is_dir()
                else artifact_root / "candidate" / "tables"
            )
            for table_path in sorted(table_dir.glob("table-*.json")):
                table = json.loads(table_path.read_text(encoding="utf-8"))
                if source.page not in table.get("source_pages", []):
                    continue
                headers = [str(value) for value in table.get("headers") or []]
                rows = table.get("rows") or []
                markdown = "\n".join(
                    [
                        "| " + " | ".join(headers) + " |",
                        "| " + " | ".join("---" for _ in headers) + " |",
                    ]
                    + [
                        "| " + " | ".join(str(row.get(header, "")) for header in headers) + " |"
                        for row in rows
                    ]
                )
                try:
                    return cls(parse_benefit_table(markdown, source))
                except ValueError:
                    continue
            raise ValueError(f"No benefit rows found for canonical page {path}")

    def resolve(self, query: str) -> ResolvedBenefit | None:
        code_match = re.search(r"\bD\d{4}\b", query, flags=re.IGNORECASE)
        if not code_match:
            return None
        code = code_match.group(0).upper()
        rule = CODE_RULES.get(code)
        if not rule:
            return None
        candidates = [
            record
            for record in self.records
            if record.benefit_class == rule["benefit_class"]
            and rule["term"].lower() in record.description.lower()
        ]
        if not candidates:
            raise LookupError(f"No structured benefit row found for {code}")
        return ResolvedBenefit(code=code, service=rule["service"], record=candidates[0])
