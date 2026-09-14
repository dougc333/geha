"""Generate one synthetic claim form, then degrade it harder than
README_OCR_PIPELINE.md's original garbling (which only did rotation/crop,
gaussian blur, random lines, speckle noise).

This adds on top of that: perspective warp, a lighting gradient (uneven
scan illumination), heavier salt-and-pepper noise, and low-quality JPEG
recompression -- stacked, not just one effect at a time.

All data is fabricated. Synthetic test only.
"""

import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
random.seed(7)
np.random.seed(7)

FIELDS = [
    ("Patient Name", "Jordan T. Mireles"),
    ("Member ID", "GEHA-8837291"),
    ("Date of Service", "03/14/2026"),
    ("Diagnosis (ICD-10)", "M54.50"),
    ("Procedure (CPT)", "99214"),
    ("Charge Amount", "$186.00"),
    ("Provider NPI", "1749283650"),
    ("Facility", "Ridgeline Family Clinic"),
]

W, H = 900, 620


def render_clean_form() -> Image.Image:
    img = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
    value_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)

    draw.text(
        (40, 30),
        "SYNTHETIC CLAIM FORM -- FABRICATED TEST DATA",
        font=title_font,
        fill=0,
    )
    draw.line((40, 70, W - 40, 70), fill=0, width=2)

    y = 110
    for label, value in FIELDS:
        draw.text((50, y), label.upper(), font=label_font, fill=90)
        draw.text((50, y + 20), value, font=value_font, fill=0)
        draw.line((50, y + 50, W - 50, y + 50), fill=180, width=1)
        y += 62

    return img


def degrade(img: Image.Image) -> Image.Image:
    arr = np.array(img)

    # 1. Perspective warp (a crooked photo/scan, not just a rotation).
    h, w = arr.shape
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    jitter = 28
    dst = np.float32(
        [
            [random.uniform(0, jitter), random.uniform(0, jitter)],
            [w - random.uniform(0, jitter), random.uniform(0, jitter * 1.6)],
            [random.uniform(0, jitter * 1.6), h - random.uniform(0, jitter)],
            [w - random.uniform(0, jitter), h - random.uniform(0, jitter)],
        ]
    )
    m = cv2.getPerspectiveTransform(src, dst)
    arr = cv2.warpPerspective(arr, m, (w, h), borderValue=255)

    # 2. Uneven scan illumination: a lighting gradient across the page.
    gradient = np.tile(np.linspace(-55, 25, w), (h, 1))
    arr = np.clip(arr.astype(np.float32) + gradient, 0, 255).astype(np.uint8)

    # 3. Random occluding strokes (coffee-cup arc, stray pen lines, staple shadow).
    for _ in range(9):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = x1 + random.randint(-160, 160), y1 + random.randint(-40, 40)
        cv2.line(
            arr,
            (x1, y1),
            (x2, y2),
            color=int(random.choice([30, 210])),
            thickness=random.choice([1, 2, 3]),
        )
    cv2.ellipse(
        arr, (int(w * 0.78), int(h * 0.22)), (70, 55), 0, 0, 360, color=140, thickness=3
    )

    # 4. Gaussian blur -- heavier than the original pipeline's.
    arr = cv2.GaussianBlur(arr, (5, 5), sigmaX=1.8)

    # 5. Salt-and-pepper noise, denser than a light dusting.
    density = 0.035
    mask = np.random.random(arr.shape)
    arr[mask < density / 2] = 0
    arr[mask > 1 - density / 2] = 255

    # 6. Contrast crush (washed-out photocopy-of-a-photocopy look).
    arr = np.clip((arr.astype(np.float32) - 128) * 0.72 + 128 + 12, 0, 255).astype(
        np.uint8
    )

    degraded = Image.fromarray(arr)

    # 7. Low-quality JPEG recompression artifacts, applied last.
    tmp = ROOT / "_jpeg_tmp.jpg"
    degraded.convert("RGB").save(tmp, quality=22)
    result = Image.open(tmp).convert("L")
    tmp.unlink()
    return result


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    clean = render_clean_form()
    clean.save(ROOT / "form_clean_reference.png")

    noisy = degrade(clean)
    noisy.save(ROOT / "form_noisy.png")

    (ROOT / "ground_truth.json").write_text(
        json.dumps({label: value for label, value in FIELDS}, indent=2)
    )
    print(f"Wrote {ROOT / 'form_noisy.png'} and ground_truth.json")


if __name__ == "__main__":
    main()
