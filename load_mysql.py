"""
Create the MySQL schema for resolved claim forms and load the vector-resolved
OCR data into it. The table schema matches the CMS-1500 form fields.

Steps:
  1. Connect to the geha-mysql Docker container (geha_claims DB).
  2. DROP + CREATE table `claims_resolved` with columns for each form field
     plus `ocr_text` and `source_image`.
  3. For each garbled form, resolve its OCR blob via the vector DB, then
     INSERT a row. Fields that could NOT be resolved (or were blank) are
     stored as NULL.
  4. The missing-field metadata (missing_data + csv list) is computed in the
     SQL step (load_missing_metadata.sql), not here.

Usage:  python load_mysql.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pymysql

import build_vector_db as vdb

HERE = Path(__file__).parent
DB = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "geha_root",
    "database": "geha_claims",
}

# Form fields -> (sql column, sql type). Schema MATCHES the CMS-1500 form fields.
SCHEMA = {
    "claim_id": "VARCHAR(20) PRIMARY KEY",
    "source_image": "VARCHAR(100)",
    "patient_name": "VARCHAR(120)",
    "patient_dob": "VARCHAR(10)",
    "patient_sex": "CHAR(1)",
    "member_id": "VARCHAR(20)",
    "diagnosis": "VARCHAR(12)",
    "cpt": "VARCHAR(10)",
    "pos": "VARCHAR(2)",
    "dos": "VARCHAR(10)",
    "charge": "DECIMAL(10,2)",
    "auth_number": "VARCHAR(20)",
    "provider": "VARCHAR(120)",
    "npi": "VARCHAR(10)",
    "facility": "VARCHAR(160)",
    "ocr_text": "TEXT",
    # metadata columns for missing-data detection
    "missing_data": "VARCHAR(3) DEFAULT 'No'",
    "missing_fields": "TEXT NULL",
}


def build_ddl() -> str:
    cols = ", ".join(f"`{c}` {t}" for c, t in SCHEMA.items())
    return f"CREATE TABLE IF NOT EXISTS claims_resolved ({cols});"


def connect():
    return pymysql.connect(**DB, autocommit=True)


def main():
    # Build + load vector resolver (reuses build_vector_db)
    resolver = vdb.VectorResolver()

    # Load ground truth for claim ids + per-form OCR text
    gt = json.loads((HERE / "claim_forms_garbled" / "ground_truth.json").read_text())
    ocr_dir = HERE / "ocr_output"

    conn = connect()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS claims_resolved")
    cur.execute(build_ddl())
    print("Created table claims_resolved")

    # Load each form's resolved values
    for c in gt:
        cid = c["claim_id"]
        ocr_path = ocr_dir / f"{cid}.ocrtext"
        ocr_text = ocr_path.read_text() if ocr_path.exists() else ""
        resolved = vdb.resolve_all(resolver, ocr_text)

        # Build row dict: resolved values; missing -> None
        row: dict = {"claim_id": cid, "source_image": f"{cid}.png"}
        mapping = {
            "patient_name": "patient_name",
            "patient_dob": "patient_dob",
            "patient_sex": "patient_sex",
            "member_id": "member_id",
            "diagnosis": "diagnosis",
            "cpt": "cpt",
            "pos": "pos",
            "dos": "dos",
            "charge": "charge",
            "auth_number": "auth_number",
            "provider": "provider",
            "npi": "npi",
            "facility": "facility",
        }
        for canon, col in mapping.items():
            val = resolved.get(canon)
            if val:
                row[col] = float(val) if col == "charge" else val
        row["ocr_text"] = ocr_text

        cols = list(SCHEMA.keys())
        vals = [row.get(col) for col in cols]
        ph = ", ".join(["%s"] * len(cols))
        sql = f"INSERT INTO claims_resolved ({', '.join('`' + c + '`' for c in cols)}) VALUES ({ph})"
        cur.execute(sql, vals)
        print(f"  inserted {cid}: resolved={ {k: v for k, v in resolved.items()} }")

    conn.close()
    print("\nLoaded resolved claims into MySQL (geha_claims.claims_resolved)")


if __name__ == "__main__":
    main()
