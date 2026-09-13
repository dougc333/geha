"""Actual image-cleaning pipeline (not just vision-reading it): denoise,
normalize uneven lighting, deskew, binarize -- then OCR both the raw noisy
image and the cleaned one, and score both against ground truth.
"""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent


def deskew_angle(binary: np.ndarray) -> float:
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    return -angle if abs(angle) < 20 else 0.0  # ignore wild outliers


def clean(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    # 1. Kill salt-and-pepper first -- median blur is the right tool for it,
    #    unlike a gaussian blur which just smears it around.
    denoised = cv2.medianBlur(img, 3)
    denoised = cv2.fastNlMeansDenoising(denoised, h=12, templateWindowSize=7, searchWindowSize=21)

    # 2. CLAHE fixes the uneven scan-lighting gradient locally instead of
    #    one global contrast stretch, which would blow out the dark side.
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16, 16))
    normalized = clahe.apply(denoised)

    # 3. Adaptive threshold -- robust to the lighting gradient a single
    #    global threshold would fail on.
    binary = cv2.adaptiveThreshold(
        normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    # 4. Deskew using the dominant angle of the ink pixels themselves --
    #    this corrects rotation, not the full perspective warp (that needs a
    #    detectable page border, which a borderless scan like this doesn't
    #    have -- an honest limit of this pipeline, not hidden).
    angle = deskew_angle(255 - binary)
    h, w = binary.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    deskewed = cv2.warpAffine(binary, m, (w, h), borderValue=255, flags=cv2.INTER_CUBIC)

    # 5. Light morphological close to reknit characters the noise punched
    #    holes in, without thickening stray lines into blobs.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    closed = cv2.morphologyEx(deskewed, cv2.MORPH_CLOSE, kernel)

    return closed


def ocr(image_path: Path) -> str:
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "--psm", "6"],
        capture_output=True, text=True,
    )
    return result.stdout


def score(ocr_text: str, ground_truth: dict) -> tuple[int, int, list[str]]:
    hits, misses = 0, []
    flat = ocr_text.replace(" ", "").replace("\n", "").upper()
    for label, value in ground_truth.items():
        needle = value.replace(" ", "").upper()
        if needle in flat:
            hits += 1
        else:
            misses.append(f"{label}: expected {value!r}")
    return hits, len(ground_truth), misses


def main() -> None:
    ground_truth = json.loads((ROOT / "ground_truth.json").read_text())

    cleaned = clean(ROOT / "form_noisy.png")
    cv2.imwrite(str(ROOT / "form_cleaned.png"), cleaned)

    raw_text = ocr(ROOT / "form_noisy.png")
    (ROOT / "ocr_raw.txt").write_text(raw_text)

    clean_text = ocr(ROOT / "form_cleaned.png")
    (ROOT / "ocr_cleaned.txt").write_text(clean_text)

    raw_hits, total, raw_misses = score(raw_text, ground_truth)
    clean_hits, _, clean_misses = score(clean_text, ground_truth)

    report = {
        "fields_total": total,
        "raw_ocr": {"exact_field_hits": raw_hits, "misses": raw_misses},
        "cleaned_ocr": {"exact_field_hits": clean_hits, "misses": clean_misses},
    }
    (ROOT / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
