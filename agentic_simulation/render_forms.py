"""
Render CMS-1500-style claim form images for the 20 GEHA sample claims.

Draws a faithful CMS-1500 layout (33 numbered boxes + Box 24 service-line
grid) with PIL, filling each field from claims/claims.json. Outputs one PNG
per claim into forms/.

Usage:
    python render_forms.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CLAIMS = json.loads((Path(__file__).parent / "claims" / "claims.json").read_text())
OUT = Path(__file__).parent / "forms"
OUT.mkdir(parents=True, exist_ok=True)

# Adjudication results from simulate_flow.py -> status + member responsibility
_TRAILS = Path(__file__).parent / "claims" / "audit_trails.json"
TRAILS = json.loads(_TRAILS.read_text()) if _TRAILS.exists() else {}

# --- Layout geometry ---------------------------------------------------------
W, H = 1654, 1276  # ~A4 at 200 DPI (2:1-ish), red-ink form look
MARGIN = 40
X0, Y0 = MARGIN, MARGIN
RED = (180, 30, 30)
DARK = (30, 30, 30)
LIGHT = (245, 245, 245)


# Fonts (try to find a DejaVu Sans available on the system)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    import glob

    cands = []
    for pat in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        cands.append(pat)
    fam = glob.glob("/System/Library/Fonts/*.ttc") + glob.glob(
        "/System/Library/Fonts/Supplemental/*.ttf"
    )
    cands += fam
    for p in cands:
        try:
            f = ImageFont.truetype(p, size)
            return f
        except Exception:
            continue
    return ImageFont.load_default()


FONT = {s: _font(s) for s in (13, 15, 17, 20, 24, 28)}
FONT_B = {s: _font(s, bold=True) for s in (13, 15, 17, 20, 24, 28)}


def draw_grid(d: ImageDraw.Draw, rect, nx, ny, xl=0, yl=0, xr=0, yb=0):
    """Draw a grid inside rect with nx columns / ny rows (labels inset xl,xr etc.)."""
    x0, y0, x1, y1 = rect
    w = x1 - x0
    h = y1 - y0
    for i in range(nx + 1):
        xx = x0 + i * w / nx
        d.line([(xx, y0), (xx, y1)], fill=RED, width=1)
    for j in range(ny + 1):
        yy = y0 + j * h / ny
        d.line([(x0, yy), (x1, yy)], fill=RED, width=1)


def box(d: ImageDraw.Draw, rect, title, lines, fill=None):
    """Draw a titled CMS-1500 box. rect=(x0,y0,x1,y1). lines = list of (label,value)."""
    x0, y0, x1, y1 = rect
    if fill:
        d.rectangle(rect, fill=fill)
    d.rectangle(rect, outline=RED, width=2)
    # Title strip at top
    d.line([(x0, y0 + 26), (x1, y0 + 26)], fill=RED, width=1)
    d.text((x0 + 5, y0 + 2), title, font=FONT[13], fill=RED)
    ty = y0 + 34
    for label, value in lines:
        if label:
            d.text((x0 + 6, ty), label + ":", font=FONT[13], fill=DARK)
            vx = x0 + 6 + d.textlength(label + ":", font=FONT[13]) + 4
        else:
            vx = x0 + 6
        d.text((vx, ty), value, font=FONT[15], fill=DARK)
        ty += 24


def render(claim: dict, path: Path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Header
    d.text((X0 + 8, Y0), "HEALTH INSURANCE CLAIM FORM", font=FONT_B[28], fill=DARK)
    d.text(
        (X0 + 8, Y0 + 34),
        "APPROVED BY NATIONAL UNIFORM CLAIM COMMITTEE (NUCC) 0312",
        font=FONT[15],
        fill=DARK,
    )
    d.text((W - MARGIN - 260, Y0 + 10), "GEHA", font=FONT_B[24], fill=RED)
    d.text(
        (W - MARGIN - 300, Y0 + 40),
        "GOVERNMENT EMPLOYEES HEALTH ASSOC.",
        font=FONT[13],
        fill=DARK,
    )

    top = Y0 + 68
    bw = W - 2 * MARGIN
    # Box row 1: 1, 1a, 2, 3
    b1 = (X0, top, X0 + 180, top + 66)
    box(d, b1, "1.", [("MEDICARE x  MEDICAID x  TRICARE", "")], fill=LIGHT)
    # actual plan check
    d.text((X0 + 12, top + 36), "GROUP x   OTHER x", font=FONT[13], fill=RED)
    b1a = (X0 + 180, top, X0 + 360, top + 66)
    box(d, b1a, "1a. INSURED'S I.D. NUMBER", [("", claim["insured_id"])])
    b2 = (X0 + 360, top, X0 + 1110, top + 66)
    box(d, b2, "2. PATIENT'S NAME (Last, First, MI)", [("", claim["patient_name"])])
    b3 = (X0 + 1110, top, X0 + bw, top + 66)
    box(d, b3, "3. BIRTH DATE  SEX", [("", claim["patient_dob"])])
    d.text(
        (X0 + 1110 + 150, top + 40),
        f"  {claim['patient_sex']}",
        font=FONT[17],
        fill=DARK,
    )

    top += 66
    # Row 2: 4, 5, 6, 7
    b4 = (X0, top, X0 + 260, top + 60)
    box(d, b4, "4. INSURED'S NAME", [("", claim["insured_name"])])
    b5 = (X0 + 260, top, X0 + 940, top + 60)
    box(d, b5, "5. PATIENT'S ADDRESS", [("", claim["patient_address"])])
    b6 = (X0 + 940, top, X0 + 1180, top + 60)
    box(d, b6, "6. REL. TO INSURED", [("", claim["patient_relationship"])])
    b7 = (X0 + 1180, top, X0 + bw, top + 60)
    box(d, b7, "7. INSURED'S ADDRESS", [("", claim["patient_address"])])

    top += 60
    # Row 3: 9, 10, 11, 12
    b9 = (X0, top, X0 + 260, top + 60)
    box(d, b9, "9. OTHER INSURED'S NAME", [("", "")])
    b10 = (X0 + 260, top, X0 + 780, top + 60)
    box(
        d,
        b10,
        "10. CONDITION RELATED TO",
        [("a. Employment [ ]", ""), ("b. Auto [ ]", "")],
    )
    d.text((X0 + 266, top + 44), "c. Other [ ]", font=FONT[13], fill=DARK)
    b11 = (X0 + 780, top, X0 + 1240, top + 60)
    box(d, b11, "11. INSURED'S POLICY/GROUP #", [("", claim["insured_id"])])
    b12 = (X0 + 1240, top, X0 + bw, top + 60)
    box(d, b12, "12. PATIENT SIGNATURE", [("", "Signature on file")])

    top += 60
    # Row 4: 14, 15, 16, 17, 21, 23
    b14 = (X0, top, X0 + 280, top + 60)
    box(
        d,
        b14,
        "14. DATE CURRENT ILLNESS",
        [("", claim["service_lines"][0]["from_date"])],
    )
    b15 = (X0 + 280, top, X0 + 560, top + 60)
    box(d, b15, "15. OTHER DATE", [("", "")])
    b16 = (X0 + 560, top, X0 + 840, top + 60)
    box(d, b16, "16. DATES UNABLE TO WORK", [("", "")])
    b17 = (X0 + 840, top, X0 + 1140, top + 60)
    box(d, b17, "17. REFERRING PROVIDER", [("", "")])
    b21 = (X0 + 1140, top, X0 + bw - 220, top + 60)
    box(d, b21, "21. DIAGNOSIS (ICD-10)", [("A", claim["diagnosis"]["code"])])
    b23 = (X0 + bw - 220, top, X0 + bw, top + 60)
    box(d, b23, "23. PRIOR AUTH #", [("", "")])

    top += 60
    # Box 24 header row + service-line grid (rows A-J)
    b24 = (X0, top, X0 + bw, top + 300)
    d.rectangle(b24, outline=RED, width=2)
    d.line([(b24[0], b24[1] + 26), (b24[2], b24[1] + 26)], fill=RED, width=1)
    d.text(
        (b24[0] + 8, b24[1] + 2),
        "24.  A. DATES (MM/DD/YY)      B. POS       D. CPT/HCPCS       E. MOD       F. DX        G. $ CHARGES       H. UNITS       J. NPI",
        font=FONT[13],
        fill=RED,
    )
    # draw column separators
    cols = [0.12, 0.26, 0.50, 0.60, 0.70, 0.83, 0.91, 1.0]
    for c in cols:
        xx = b24[0] + c * bw
        d.line([(xx, b24[1] + 26), (xx, b24[3])], fill=RED, width=1)
    # service line rows
    sl_x0 = b24[0] + 6
    row_h = 34
    for r, sl in enumerate(claim["service_lines"][:6]):
        ry = b24[1] + 34 + r * row_h
        d.text((sl_x0, ry), f"{chr(65 + r)}", font=FONT[13], fill=RED)
        d.text((sl_x0 + 30, ry), sl["from_date"], font=FONT[15], fill=DARK)
        d.text(
            (sl_x0 + 0.12 * bw + 10, ry),
            sl["place_of_service"],
            font=FONT[15],
            fill=DARK,
        )
        d.text((sl_x0 + 0.26 * bw + 10, ry), sl["cpt"], font=FONT[15], fill=DARK)
        d.text(
            (sl_x0 + 0.50 * bw + 10, ry),
            sl["modifier"] or "-",
            font=FONT[15],
            fill=DARK,
        )
        d.text((sl_x0 + 0.60 * bw + 10, ry), sl["dx_pointer"], font=FONT[15], fill=DARK)
        d.text(
            (sl_x0 + 0.70 * bw + 10, ry),
            f"${sl['charge']:.2f}",
            font=FONT[15],
            fill=DARK,
        )
        d.text((sl_x0 + 0.83 * bw + 10, ry), str(sl["units"]), font=FONT[15], fill=DARK)
        d.text(
            (sl_x0 + 0.91 * bw + 10, ry), sl["rendering_npi"], font=FONT[15], fill=DARK
        )
        d.line([(b24[0], ry + row_h), (b24[2], ry + row_h)], fill=RED, width=1)

    top += 300
    # Row: 25, 26, 27, 28, 29, 30, 31
    b25 = (X0, top, X0 + 220, top + 56)
    box(d, b25, "25. FED TAX ID", [("", "XX-XXXXXXX")])
    b26 = (X0 + 220, top, X0 + 440, top + 56)
    box(d, b26, "26. PATIENT ACCT #", [("", claim["claim_id"])])
    b27 = (X0 + 440, top, X0 + 640, top + 56)
    box(d, b27, "27. ACCEPT ASSIGN?", [("", "Y")])
    b28 = (X0 + 640, top, X0 + 820, top + 56)
    box(d, b28, "28. TOTAL CHARGE", [("", f"${claim['total_charge']:.2f}")])
    b29 = (X0 + 820, top, X0 + 1000, top + 56)
    box(d, b29, "29. AMOUNT PAID", [("", "$0.00")])
    b30 = (X0 + 1000, top, X0 + 1180, top + 56)
    box(d, b30, "30. RESERVED", [("", "")])
    b31 = (X0 + 1180, top, X0 + bw, top + 56)
    box(d, b31, "31. SIGNATURE OF PHYSICIAN", [("", "S.O.F.")])

    top += 56
    # Row: 32, 33
    b32 = (X0, top, X0 + 820, top + 70)
    box(
        d,
        b32,
        "32. SERVICE FACILITY",
        [("", claim["facility"]["name"]), ("", claim["facility"]["address"])],
    )
    b33 = (X0 + 820, top, X0 + bw, top + 70)
    box(
        d,
        b33,
        "33. BILLING PROVIDER INFO & PH#",
        [
            ("", claim["facility"]["name"]),
            ("", "NPI: " + claim["service_lines"][0]["rendering_npi"]),
        ],
    )

    # Footer status stamp (prefer the simulation's adjudicated status)
    trail = next((t for t in TRAILS if t.get("claim_id") == claim["claim_id"]), {})
    status = trail.get("final_status", claim.get("status", "PAID"))
    color = {
        "PAID": (20, 130, 40),
        "PARTIAL": (200, 120, 0),
        "PENDING_REVIEW": (100, 100, 200),
        "DENIED": (190, 30, 30),
    }.get(status, DARK)
    d.text(
        (X0 + 8, H - 90),
        f"SIMULATED CLAIM  {claim['claim_id']}  |  STATUS: {status}",
        font=FONT_B[20],
        fill=color,
    )
    d.text(
        (X0 + 8, H - 60),
        f"Plan: {claim['plan']}   |   Diagnosis: {claim['diagnosis']['code']} "
        f"{claim['diagnosis']['description'][:50]}",
        font=FONT[15],
        fill=DARK,
    )

    img.save(path)
    print(f"  wrote {path.name}  status={status} total=${claim['total_charge']:.2f}")


if __name__ == "__main__":
    for c in CLAIMS:
        render(c, OUT / f"{c['claim_id']}.png")
    print(f"\nRendered {len(CLAIMS)} claim forms to {OUT}")
