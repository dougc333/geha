"""
Generate 20 sample GEHA medical insurance claims.

Each claim is a realistic CMS-1500-style record: patient + insured info,
diagnosis (ICD-10), one or more service lines (CPT/HCPCS codes, dates,
place of service, charges, units), and billing/servicing providers (NPIs).

Outputs:
    claims/claims.json   - full structured records
    claims/claims.csv    - flattened row per service line
"""

from __future__ import annotations

import csv
import json
import random
import uuid
from pathlib import Path

random.seed(7)

OUT = Path(__file__).parent / "claims"
OUT.mkdir(parents=True, exist_ok=True)

# --- GEHA plan types (FEHB = Federal Employees Health Benefits) ---------------
PLANS = [
    "GEHA Elevate Plus (HDHP)",
    "GEHA Standard",
    "GEHA High",
    "GEHA Elevate (HDHP)",
    "GEHA Medical Benefit (PSHB)",
]

# --- Patient / member generator ----------------------------------------------
FIRST = [
    "James",
    "Maria",
    "Robert",
    "Linda",
    "Michael",
    "Susan",
    "William",
    "Karen",
    "David",
    "Nancy",
    "Richard",
    "Barbara",
    "Joseph",
    "Aisha",
    "Thomas",
    "Priya",
    "Charles",
    "Donna",
    "Christopher",
    "Elena",
    "Daniel",
    "Sandra",
    "Matthew",
    "Yusuf",
    "Anthony",
    "Grace",
    "Mark",
    "Hannah",
    "Donald",
    "Rachel",
]
LAST = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
]

DISEASES = [
    # (icd10, description, [cpt, description, typical_charge, place_of_service])
    (
        "J06.9",
        "Acute upper respiratory infection, unspecified",
        [("99213", "Office visit, established patient", 155.00, "11")],
    ),
    (
        "M54.5",
        "Low back pain",
        [
            ("99214", "Office visit, established patient", 210.00, "11"),
            ("97140", "Manual therapy", 85.00, "11"),
        ],
    ),
    (
        "E11.9",
        "Type 2 diabetes mellitus without complications",
        [
            ("99215", "Office visit, established patient", 265.00, "11"),
            ("83036", "HbA1c test", 45.00, "11"),
        ],
    ),
    (
        "I10",
        "Essential (primary) hypertension",
        [("99214", "Office visit, established patient", 215.00, "11")],
    ),
    (
        "K21.9",
        "Gastro-esophageal reflux disease without esophagitis",
        [
            ("99213", "Office visit, established patient", 160.00, "11"),
            ("91034", "Esophageal pH test", 320.00, "11"),
        ],
    ),
    (
        "F41.1",
        "Generalized anxiety disorder",
        [("90834", "Psychotherapy 45 min", 175.00, "11")],
    ),
    (
        "S93.401A",
        "Sprain of unspecified foot, initial encounter",
        [
            ("99213", "Office visit", 150.00, "11"),
            ("73630", "X-ray foot, 3 views", 130.00, "11"),
        ],
    ),
    (
        "Z23",
        "Encounter for immunization",
        [
            ("90670", "Pneumococcal vaccine PCV20", 250.00, "11"),
            ("90471", "Immunization administration", 35.00, "11"),
        ],
    ),
    (
        "N39.0",
        "Urinary tract infection, site not specified",
        [
            ("99213", "Office visit", 158.00, "11"),
            ("81003", "Urinalysis, automated", 28.00, "11"),
        ],
    ),
    (
        "J45.909",
        "Unspecified asthma, uncomplicated",
        [("99214", "Office visit", 230.00, "11"), ("94010", "Spirometry", 95.00, "11")],
    ),
    (
        "H25.13",
        "Age-related nuclear cataract, bilateral",
        [
            ("99204", "New patient office visit", 310.00, "11"),
            ("92004", "Comprehensive eye exam", 260.00, "22"),
        ],
    ),
    (
        "K08.101",
        "Partial loss of teeth, unspecified cause, class I",
        [("D0150", "Comprehensive oral evaluation", 190.00, "11")],
    ),
    (
        "G47.33",
        "Obstructive sleep apnea (adult)",
        [
            ("99214", "Office visit", 225.00, "11"),
            ("95782", "Polysomnography attended", 1450.00, "21"),
        ],
    ),
    (
        "M17.0",
        "Bilateral primary osteoarthritis of knee",
        [
            ("99214", "Office visit", 240.00, "11"),
            ("73564", "X-ray knee, 4 views", 150.00, "11"),
        ],
    ),
    (
        "Z01.810",
        "Encounter for pre-procedural cardiovascular examination",
        [("99204", "New patient office visit", 330.00, "11")],
    ),
    (
        "L20.9",
        "Atopic dermatitis, unspecified",
        [("99213", "Office visit", 155.00, "11")],
    ),
    (
        "K35.80",
        "Unspecified acute appendicitis",
        [
            ("99283", "ED visit high severity", 780.00, "23"),
            ("74178", "CT abdomen and pelvis with contrast", 950.00, "23"),
        ],
    ),
    (
        "Z00.00",
        "Encounter for general adult medical examination",
        [("99396", "Periodic comprehensive preventive", 220.00, "11")],
    ),
    (
        "D25.9",
        "Uterine leiomyoma, unspecified",
        [
            ("99214", "Office visit", 245.00, "11"),
            ("76830", "Transvaginal ultrasound", 290.00, "11"),
        ],
    ),
    (
        "J18.9",
        "Pneumonia, unspecified organism",
        [
            ("99214", "Office visit", 235.00, "11"),
            ("71045", "Chest X-ray single view", 120.00, "11"),
        ],
    ),
]

HOSPITALS = [
    ("St. Mary's Medical Center", "300 N 1st Ave, Kansas City, MO 64101"),
    ("Community Health Clinic", "1500 Main St, Springfield, VA 22150"),
    ("Capital Physician Group", "800 K St NW, Washington, DC 20001"),
    ("Fairfax Family Practice", "55 Madison St, Fairfax, VA 22030"),
    ("Apex Orthopedic Associates", "1200 Duke St, Alexandria, VA 22314"),
    ("Midwest Cardiology Clinic", "901 Grand Blvd, Kansas City, MO 64106"),
    ("Northgate Family Medicine", "75 River Rd, Bethesda, MD 20817"),
    ("Riverside Imaging Center", "45 Lakeview Dr, Rockville, MD 20850"),
]

# Rendering provider NPI pool (billing = rendering here for simplicity)
NPIS = [
    "1982635411",
    "1674892022",
    "1325478890",
    "1452378901",
    "1098723456",
    "1554981234",
    "1876543290",
    "1432569871",
]


def npi() -> str:
    return random.choice(NPIS)


def phone() -> str:
    return f"({random.randint(200, 989)}) {random.randint(200, 989)}-{random.randint(1000, 9999)}"


def build_claim(i: int, forced_diag: tuple | None = None) -> dict:
    diag = forced_diag if forced_diag else random.choice(DISEASES)
    icd10, desc, cpts = diag
    patient_fn = random.choice(FIRST)
    patient_ln = random.choice(LAST)
    insured = f"{patient_ln}, {patient_fn}"  # assume self-insured for simplicity
    rel = "Self"
    gender = random.choice(["M", "F"])
    yob = random.randint(1948, 2002)
    mob = random.randint(1, 12)
    dob = f"{mob:02d}/{random.randint(1, 28):02d}/{yob}"
    addr = f"{random.randint(10, 9999)} {random.choice(['Elm', 'Oak', 'Maple', 'Cedar', 'Birch', 'Pine'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Ln', 'Ct'])}"
    city = random.choice(
        [
            "Arlington",
            "Silver Spring",
            "Washington",
            "Bethesda",
            "Reston",
            "Alexandria",
            "Tysons",
            "Rockville",
            "Annandale",
        ]
    )
    state = random.choice(["VA", "MD", "DC", "VA", "MD", "VA"])
    zipc = random.choice(
        [
            "22041",
            "20904",
            "20001",
            "20814",
            "20191",
            "22314",
            "22182",
            "20850",
            "22003",
        ]
    )
    member_id = f"G{f'y{1000 + i * 17:06d}'}"

    # Date of service (within last ~60 days)
    dos = random.choice([1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21, 24, 28])
    month = random.choice([6, 7, 8])
    year = "2026"

    # Choose provider
    facility = random.choice(HOSPITALS)
    fac_name, fac_addr = facility
    fac_city = fac_addr.split(",")[1].strip().split()[0]

    service_lines = []
    total = 0.0
    for cpt, cpt_desc, charge, pos in cpts:
        total += charge
        service_lines.append(
            {
                "from_date": f"{month:02d}/{dos:02d}/{year}",
                "to_date": f"{month:02d}/{dos:02d}/{year}",
                "place_of_service": pos,
                "cpt": cpt,
                "cpt_desc": cpt_desc,
                "modifier": "",
                "dx_pointer": "A",
                "charge": charge,
                "units": 1,
                "rendering_npi": npi(),
            }
        )

    # Simple adjudication status distribution for realism
    status = random.choices(
        ["PAID", "PARTIAL", "PENDING_REVIEW", "DENIED"],
        weights=[13, 4, 2, 1],
    )[0]

    return {
        "claim_id": f"CLM-{100000 + i}",
        "member_id": member_id,
        "plan": random.choice(PLANS),
        "patient_name": f"{patient_ln}, {patient_fn}",
        "patient_dob": dob,
        "patient_sex": gender,
        "patient_address": f"{addr}, {city}, {state} {zipc}",
        "patient_relationship": rel,
        "insured_name": insured,
        "insured_id": member_id,
        "diagnosis": {"code": icd10, "description": desc},
        "rendering_provider": {
            "npi": npi(),
            "name": random.choice(
                [
                    "Dr. A. Bennett",
                    "Dr. S. Chen",
                    "Dr. R. Gupta",
                    "Dr. L. Okafor",
                    "Dr. J. Miller",
                    "Dr. T. Alvarez",
                    "Dr. M. Park",
                    "Dr. K. Singh",
                ]
            ),
        },
        "facility": {"name": fac_name, "address": fac_addr},
        "service_lines": service_lines,
        "total_charge": round(total, 2),
        "status": status,
        "submitted_date": f"0{random.randint(1, 9)}/{random.randint(1, 28):02d}/2026",
        "received_date": f"0{random.randint(1, 9)}/{random.randint(1, 28):02d}/2026",
    }


claims = []
for i in range(20):
    # Force a few claims onto non-covered services so the simulation
    # realistically shows PAID / PARTIAL / DENIED outcomes.
    forced = None
    if i == 2:
        forced = next(d for d in DISEASES if d[0] == "Z23")  # 90670 vaccine
    elif i == 5:
        forced = next(d for d in DISEASES if d[0] == "K08.101")  # D0150 dental
    claims.append(build_claim(i, forced))

with open(OUT / "claims.json", "w") as f:
    json.dump(claims, f, indent=2)

# Flatten to CSV (one row per service line)
rows = []
for c in claims:
    for sl in c["service_lines"]:
        rows.append(
            {
                "claim_id": c["claim_id"],
                "member_id": c["member_id"],
                "plan": c["plan"],
                "patient_name": c["patient_name"],
                "patient_dob": c["patient_dob"],
                "patient_sex": c["patient_sex"],
                "insured_id": c["insured_id"],
                "diagnosis_code": c["diagnosis"]["code"],
                "diagnosis_desc": c["diagnosis"]["description"],
                "facility": c["facility"]["name"],
                "dos_from": sl["from_date"],
                "dos_to": sl["to_date"],
                "pos": sl["place_of_service"],
                "cpt": sl["cpt"],
                "cpt_desc": sl["cpt_desc"],
                "dx_pointer": sl["dx_pointer"],
                "charge": sl["charge"],
                "units": sl["units"],
                "rendering_npi": sl["rendering_npi"],
                "total_charge": c["total_charge"],
                "status": c["status"],
                "submitted_date": c["submitted_date"],
            }
        )

with open(OUT / "claims.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(claims)} claims -> claims/claims.json")
print(f"Wrote {len(rows)} service-line rows -> claims/claims.csv")
print(f"Total billed: ${sum(c['total_charge'] for c in claims):,.2f}")
from collections import Counter

print("Status distribution:", dict(Counter(c["status"] for c in claims)))
