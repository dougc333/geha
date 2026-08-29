"""
OCR each garbled claim form with tesseract and write <imagename>.ocrtext.

The garbled (blurred, noised, line-crossed, handwritten) images produce noisy
OCR text. We run tesseract with psm 6 (assume a single uniform block) which
yields one big text blob per form; the blob is saved verbatim to
ocr_output/<claimid>.ocrtext. Later stages parse/vectorize this blob.

Usage:  python ocr_forms.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

FORMS = Path(__file__).parent / "claim_forms_garbled"
OUT = Path(__file__).parent / "ocr_output"
OUT.mkdir(parents=True, exist_ok=True)

TESS = "/opt/homebrew/bin/tesseract"


def ocr(path: Path) -> str:
    r = subprocess.run(
        [TESS, str(path), "stdout", "--psm", "6"],
        capture_output=True, text=True)
    return r.stdout


def main():
    forms = sorted(FORMS.glob("*.png"))
    results = {}
    for f in forms:
        text = ocr(f)
        ocr_path = OUT / f"{f.stem}.ocrtext"
        ocr_path.write_text(text)
        results[f.stem] = text
        print(f"{f.stem}: {len(text.split())} tokens")
    # A combined index too
    (OUT / "_all_ocr.txt").write_text(
        "\n\n=====FORM=====\n\n".join(f"{k}\n{v}" for k, v in results.items()))
    print(f"\nWrote {len(forms)} .ocrtext files to {OUT}/")


if __name__ == "__main__":
    main()
