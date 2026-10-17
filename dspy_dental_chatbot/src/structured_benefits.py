"""SQLite-backed deterministic lookup for the dental benefit comparison table."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
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
        """Serialize one database row so the LLM never aligns table columns."""
        payload = {
            "evidence_type": "sqlite_benefit_lookup",
            "lookup_key": self.code,
            "service": self.service,
            "benefit_class": self.record.benefit_class,
            "benefit_description": self.record.description,
            "high_cost": self.record.high_cost,
            "standard_in_network_cost": self.record.standard_in_network_cost,
            "standard_out_of_network_cost": self.record.standard_out_of_network_cost,
            "source": asdict(self.record.source),
        }
        return "STRUCTURED BENEFIT RECORD\n" + json.dumps(payload, indent=2)


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS benefit_records (
    benefit_id INTEGER PRIMARY KEY,
    benefit_class TEXT NOT NULL,
    benefit_name TEXT NOT NULL,
    description TEXT NOT NULL,
    high_cost TEXT NOT NULL,
    standard_in_network_cost TEXT NOT NULL,
    standard_out_of_network_cost TEXT NOT NULL,
    document_id TEXT NOT NULL,
    plan_year INTEGER NOT NULL,
    source_page INTEGER NOT NULL,
    source_section TEXT NOT NULL,
    UNIQUE (
        benefit_class,
        description,
        document_id,
        plan_year,
        source_page
    )
);

CREATE TABLE IF NOT EXISTS service_rules (
    lookup_key TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    benefit_class TEXT NOT NULL,
    description_term TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS procedure_codes (
    procedure_code TEXT PRIMARY KEY,
    lookup_key TEXT NOT NULL REFERENCES service_rules(lookup_key)
);

CREATE TABLE IF NOT EXISTS service_aliases (
    alias TEXT PRIMARY KEY COLLATE NOCASE,
    lookup_key TEXT NOT NULL REFERENCES service_rules(lookup_key)
);

CREATE INDEX IF NOT EXISTS benefit_records_class_idx
    ON benefit_records(plan_year, benefit_class);
CREATE INDEX IF NOT EXISTS service_aliases_lookup_idx
    ON service_aliases(lookup_key);
"""


SERVICE_RULES = (
    ("CLEANING", "Adult prophylaxis / cleaning", "Class A", "cleanings"),
    ("EXTRACTION", "Simple extraction", "Class B", "extractions"),
    ("ROOT_CANAL", "Anterior root canal", "Class C", "root canals"),
    ("ORTHODONTICS", "Child and adult orthodontics", "Class D", "orthodontics"),
)

PROCEDURE_CODES = (
    ("D1110", "CLEANING"),
    ("D7140", "EXTRACTION"),
    ("D3310", "ROOT_CANAL"),
)

SERVICE_ALIASES = (
    ("adult cleaning", "CLEANING"),
    ("cleaning", "CLEANING"),
    ("prophylaxis", "CLEANING"),
    ("simple extraction", "EXTRACTION"),
    ("extraction", "EXTRACTION"),
    ("root canal", "ROOT_CANAL"),
    ("braces", "ORTHODONTICS"),
    ("orthodontic", "ORTHODONTICS"),
    ("orthodontics", "ORTHODONTICS"),
    ("orthodontia", "ORTHODONTICS"),
    ("aligners", "ORTHODONTICS"),
)


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
        rows.append(
            BenefitRecord(
                benefit_class=f"Class {class_match.group(1).upper()}",
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


def _source_for_page(path: Path) -> SourceRef:
    year_match = re.search(r"(20\d{2})", path.as_posix())
    page_label = path.parent.name if path.name == "page.md" else path.stem
    page_match = re.search(r"page-(\d+)$", page_label)
    if not page_match:
        raise ValueError(f"Cannot determine source page from {path}")
    return SourceRef(
        document_id="geha-dental-benefits-guide",
        plan_year=int(year_match.group(1)) if year_match else 0,
        page=int(page_match.group(1)),
        section="Dental benefit comparison",
    )


def extract_benefit_records(path: str | Path) -> list[BenefitRecord]:
    """Read the canonical page/table artifacts produced by document ingestion."""
    path = Path(path)
    source = _source_for_page(path)
    try:
        return parse_benefit_table(path.read_text(), source)
    except ValueError:
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
                return parse_benefit_table(markdown, source)
            except ValueError:
                continue
        raise ValueError(f"No benefit rows found for canonical page {path}")


def _seed_connection(connection: sqlite3.Connection, records: list[BenefitRecord]) -> None:
    connection.executescript(SCHEMA_SQL)
    with connection:
        connection.execute("DELETE FROM procedure_codes")
        connection.execute("DELETE FROM service_aliases")
        connection.execute("DELETE FROM service_rules")
        connection.execute("DELETE FROM benefit_records")
        connection.executemany(
            """
            INSERT INTO benefit_records (
                benefit_class, benefit_name, description, high_cost,
                standard_in_network_cost, standard_out_of_network_cost,
                document_id, plan_year, source_page, source_section
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.benefit_class,
                    record.benefit_name,
                    record.description,
                    record.high_cost,
                    record.standard_in_network_cost,
                    record.standard_out_of_network_cost,
                    record.source.document_id,
                    record.source.plan_year,
                    record.source.page,
                    record.source.section,
                )
                for record in records
            ],
        )
        connection.executemany(
            "INSERT INTO service_rules VALUES (?, ?, ?, ?)", SERVICE_RULES
        )
        connection.executemany(
            "INSERT INTO procedure_codes VALUES (?, ?)", PROCEDURE_CODES
        )
        connection.executemany(
            "INSERT INTO service_aliases VALUES (?, ?)", SERVICE_ALIASES
        )


def build_benefit_database(database_path: str | Path, source_page: str | Path) -> Path:
    """Atomically rebuild the runtime SQLite database from extracted evidence."""
    destination = Path(database_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        _seed_connection(connection, extract_benefit_records(source_page))
    finally:
        connection.close()
    temporary.replace(destination)
    return destination


def _record_from_row(row: sqlite3.Row) -> BenefitRecord:
    return BenefitRecord(
        benefit_class=row["benefit_class"],
        benefit_name=row["benefit_name"],
        description=row["description"],
        high_cost=row["high_cost"],
        standard_in_network_cost=row["standard_in_network_cost"],
        standard_out_of_network_cost=row["standard_out_of_network_cost"],
        source=SourceRef(
            document_id=row["document_id"],
            plan_year=row["plan_year"],
            page=row["source_page"],
            section=row["source_section"],
        ),
    )


class SQLiteBenefitStore:
    """Thread-safe, read-only runtime access to authoritative benefit rows."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    @classmethod
    def from_sqlite(cls, path: str | Path) -> "SQLiteBenefitStore":
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Benefit database not found: {path}. Run src/build_benefits_db.py."
            )
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        return cls(connection)

    @classmethod
    def from_markdown(cls, path: str | Path) -> "SQLiteBenefitStore":
        """Build an in-memory database for extraction tests and one-off tools."""
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        _seed_connection(connection, extract_benefit_records(path))
        return cls(connection)

    @property
    def records(self) -> list[BenefitRecord]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM benefit_records ORDER BY benefit_id"
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def resolve(self, query: str) -> ResolvedBenefit | None:
        code_match = re.search(r"\bD\d{4}\b", query, flags=re.IGNORECASE)
        with self._lock:
            if code_match:
                requested_key = code_match.group(0).upper()
                rule = self.connection.execute(
                    """
                    SELECT r.* FROM procedure_codes c
                    JOIN service_rules r ON r.lookup_key = c.lookup_key
                    WHERE c.procedure_code = ?
                    """,
                    (requested_key,),
                ).fetchone()
            else:
                normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
                aliases = self.connection.execute(
                    """
                    SELECT a.alias, r.* FROM service_aliases a
                    JOIN service_rules r ON r.lookup_key = a.lookup_key
                    ORDER BY length(a.alias) DESC
                    """
                ).fetchall()
                rule = next(
                    (
                        candidate
                        for candidate in aliases
                        if re.search(
                            rf"\b{re.escape(candidate['alias']).replace(r'\ ', r'\s+')}\b",
                            normalized,
                        )
                    ),
                    None,
                )
                requested_key = str(rule["lookup_key"]) if rule else ""
            if rule is None:
                return None
            row = self.connection.execute(
                """
                SELECT * FROM benefit_records
                WHERE benefit_class = ?
                  AND instr(lower(description), lower(?)) > 0
                ORDER BY plan_year DESC, benefit_id
                LIMIT 1
                """,
                (rule["benefit_class"], rule["description_term"]),
            ).fetchone()
        if row is None:
            raise LookupError(f"No structured benefit row found for {requested_key}")
        return ResolvedBenefit(
            code=requested_key,
            service=str(rule["service"]),
            record=_record_from_row(row),
        )


# Backward-compatible name for existing offline tests and callers. It is now
# backed by SQLite rather than a Python list.
StructuredBenefitIndex = SQLiteBenefitStore
