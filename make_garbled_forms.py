"""
Generate 10 synthetic CMS-1500 claim forms with GARBLED handwriting + missing data.

Pipeline per form:
  1. Build real claim data (some fields intentionally blank = "missing data").
  2. Render a clean CMS-1500 form with a HANDWRITING effect (per-glyph jitter)
     so OCR produces noisy/garbled text.
  3. Apply a computer-vision garbling filter: random crop/rotation, gaussian
     blur, and random lines/strokes across the image.
  4. Save to claim_forms_garbled/<claimid>.png

The ground-truth JSON (with which fields were blanked) is saved to
claim_forms_garbled/ground_truth.json for verification later.

Usage:  python make_garbled_forms.py
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

random.seed(31)
OUT = Path(__file__).parent / "claim_forms_garbled"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1400, 1080  # slightly smaller for OCR
RED = (170, 30, 30)
DARK = (40, 40, 40)

# ---- fonts ----
def _font(size: int, bold: bool = False):
    import glob
    cands = ["/System/Library/Fonts/Supplemental/Arial.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf"]
    cands += glob.glob("/System/Library/Fonts/Supplemental/*.ttf")
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

# Use Comic Sans MS if present for handwriting feel, else Arial w/ jitter.
_hand = None
for p in ["/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
          "/System/Library/Fonts/Supplemental/Chalkboard.ttf"]:
    if Path(p).exists():
        _hand = p
        break
F_H = ImageFont.truetype(_hand, 22) if _hand else _font(20)
F_HB = ImageFont.truetype(_hand, 26) if _hand else _font(24)
F_L = ImageFont.truetype(_hand, 16) if _hand else _font(14)


def htext(d: ImageDraw.ImageDraw, xy, text, fill=DARK, font=None, jitter=0.6):
    """Draw text with per-glyph jitter to mimic handwriting -> garbled OCR.

    Light jitter: enough that OCR makes small character errors (proving the
    vector DB's correction value), not so much that every field is destroyed.
    """
    font = font or F_H
    x, y = xy
    for ch in text:
        dx = random.uniform(-jitter, jitter)
        dy = random.uniform(-jitter, jitter)
        rot = random.uniform(-2, 2)
        d.text((x + dx, y + dy), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font)


# ---- synthetic claim data ----
PROVIDERS = ["Dr. A. Bennett", "Dr. S. Chen", "Dr. R. Gupta", "Dr. L. Okafor",
             "Dr. J. Miller", "Dr. K. Singh"]
NPIS = ["1982635411", "1674892022", "1325478890", "1452378901", "1098723456"]
FAC = ["St. Mary's Medical Center", "Community Health Clinic", "Capital Physician Group"]
DXP = ["H25.13", "E11.9", "J06.9", "M54.5", "I10", "N39.0", "G47.33"]
CPT = ["99213", "99214", "99204", "95782", "90670"]
NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]


def make_claim(i: int) -> dict:
    c = {
        "claim_id": f"SYN-{1000+i}",
        "patient_name": f"{random.choice(NAMES)}, {random.choice(['John','Mary','Robert','Ann','David','Lisa'])}",
        "patient_dob": f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/{random.randint(1940,2000)}",
        "patient_sex": random.choice(["M", "F"]),
        "member_id": f"G{1000+i:04d}",
        "diagnosis": random.choice(DXP),
        "cpt": random.choice(CPT),
        "pos": random.choice(["11", "22", "21"]),
        "dos": f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/2026",
        "charge": round(random.uniform(120, 1500), 2),
        "provider": random.choice(PROVIDERS),
        "npi": random.choice(NPIS),
        "facility": random.choice(FAC),
        "auth_number": f"AU-{random.randint(10000,99999)}",
    }
    # Deliberately blank 0-2 fields to simulate "missing data"
    blanks = random.sample(["diagnosis", "cpt", "pos", "charge", "npi", "dos"],
                           k=random.randint(0, 2))
    for b in blanks:
        c[b] = ""
    c["_missing"] = blanks
    return c


def box(d, rect, title, lines, fill=None):
    x0, y0, x1, y1 = rect
    if fill:
        d.rectangle(rect, fill=fill)
    d.rectangle(rect, outline=RED, width=2)
    d.line([(x0, y0 + 24), (x1, y0 + 24)], fill=RED, width=1)
    d.text((x0 + 5, y0 + 3), title, font=F_L, fill=RED)
    ty = y0 + 30
    for label, value in lines:
        if label:
            d.text((x0 + 6, ty), label + ":", font=F_L, fill=DARK)
            vx = x0 + 6 + d.textlength(label + ":", font=F_L) + 3
        else:
            vx = x0 + 6
        htext(d, (vx, ty), value, font=F_H)
        ty += 26


def render(claim: dict, path: Path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    X0, Y0 = 30, 30
    bw = W - 60

    d.text((X0, Y0), "HEALTH INSURANCE CLAIM FORM", font=F_HB, fill=DARK)
    d.text((X0, Y0 + 30), "G.E.H.A  -  SIMULATED", font=F_L, fill=RED)

    top = Y0 + 60
    # Row: patient name / dob / sex
    box(d, (X0, top, X0 + 620, top + 60), "2. PATIENT NAME", [("", claim["patient_name"])])
    box(d, (X0 + 620, top, X0 + 900, top + 60), "3. DOB", [("", claim["patient_dob"])])
    box(d, (X0 + 900, top, X0 + bw, top + 60), "SEX", [("", claim["patient_sex"])])
    top += 60
    # Row: member id / diag / cpt / pos
    box(d, (X0, top, X0 + 360, top + 60), "1a. MEMBER ID", [("", claim["member_id"])])
    box(d, (X0 + 360, top, X0 + 760, top + 60), "21. DIAGNOSIS (ICD-10)", [("", claim["diagnosis"])])
    box(d, (X0 + 760, top, X0 + 1080, top + 60), "24D. CPT", [("", claim["cpt"])])
    box(d, (X0 + 1080, top, X0 + bw, top + 60), "POS", [("", claim["pos"])])
    top += 60
    # Row: dos / charge / auth
    box(d, (X0, top, X0 + 400, top + 60), "24A. DATE OF SERVICE", [("", claim["dos"])])
    box(d, (X0 + 400, top, X0 + 800, top + 60), "28. TOTAL CHARGE $", [("", f"{claim['charge']:.2f}" if claim["charge"] else "")])
    box(d, (X0 + 800, top, X0 + bw, top + 60), "23. PRIOR AUTH", [("", claim["auth_number"])])
    top += 60
    # Row: provider / npi / facility
    box(d, (X0, top, X0 + 560, top + 60), "31. RENDERING PROVIDER", [("", claim["provider"])])
    box(d, (X0 + 560, top, X0 + 920, top + 60), "33a. NPI", [("", claim["npi"])])
    box(d, (X0 + 920, top, X0 + bw, top + 60), "32. FACILITY", [("", claim["facility"])])

    # CV garbling filter part 1 happens AFTER render (below).
    img.save(path)
    return img


def cv_garbling_filter(img: Image.Image, seed: int) -> Image.Image:
    """Apply computer-vision degradation: crop/rotate, blur, random lines.

    Tuned to be *challenging but recoverable*: enough noise that OCR misreads
    characters (proving the vector DB's value), not so much that nothing is
    legible. A human or a robust resolver can still recover most fields.
    """
    rnd = random.Random(seed)

    # 1. Slight rotation + crop (simulates scanning skew)
    ang = rnd.uniform(-2.5, 2.5)
    img = img.rotate(ang, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    # 2. Mild gaussian blur (out-of-focus scan)
    img = img.filter(ImageFilter.GaussianBlur(radius=rnd.uniform(0.2, 0.6)))
    # 3. A few random lines/strokes across the image (tears/scribbles)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(rnd.randint(3, 8)):
        x0 = rnd.randint(0, W); y0 = rnd.randint(0, H)
        x1 = x0 + rnd.randint(-180, 180); y1 = y0 + rnd.randint(-110, 110)
        width = rnd.randint(1, 2)
        color = (rnd.randint(40, 190), rnd.randint(40, 190), rnd.randint(40, 190),
                 rnd.randint(100, 180))
        d.line([(x0, y0), (x1, y1)], fill=color, width=width)
    # 4. Light speckle noise
    px = img.load()
    for _ in range(rnd.randint(500, 1400)):
        x = rnd.randint(0, W - 1); y = rnd.randint(0, H - 1)
        shade = rnd.randint(0, 190)
        px[x, y] = (shade, shade, shade)
    return img


def main():
    claims = [make_claim(i) for i in range(10)]
    for i, c in enumerate(claims):
        img = render(c, OUT / "tmp.png")
        img = cv_garbling_filter(img, seed=100 + i)
        img.save(OUT / f"{c['claim_id']}.png")
        print(f"wrote {c['claim_id']}.png missing={c['_missing']}")
    # ground truth
    (OUT / "ground_truth.json").write_text(json.dumps(claims, indent=2))
    # clean up temp
    (OUT / "tmp.png").unlink(missing_ok=True)
    print(f"\nWrote {len(claims)} garbled forms to {OUT}/ + ground_truth.json")


if __name__ == "__main__":
    main()
