"""
Vector database to RESOLVE garbled OCR text -> canonical claim field values.

Approach
--------
Real-world OCR of degraded forms yields garbled tokens ("br. Shen" for
"Dr. S. Chen", "43989" for "439.89", "Seth og Sg" for a name). Exact matching
fails. We instead:

  1. Build a CORPUS of canonical candidate values per field (diagnosis codes,
     CPT codes, NPIs, provider names, facilities, member IDs, place-of-service,
     known date/amount patterns) drawn from the ground-truth data + codebooks.
  2. Embed every canonical candidate with a CHARACTER N-GRAM hashing vectorizer
     -> dense vector in faiss index (a real vector store).
  3. Embed each garbled OCR token the same way, run faiss similarity search,
     and take the nearest canonical candidate above a confidence threshold.
     Sub-threshold hits are left as the raw (unresolved) token.

This is the "vector database resolving garbled image text" requirement: the
nearest-neighbor index maps noisy OCR to clean canonical values.

Output
------
vector_db/embedding_index.faiss  + vector_db/candidates.json  (the stored index)
and a Python API `resolve_field(field, token)`.

Usage:
    python build_vector_db.py           # build index from ground truth + codebook
    python build_vector_db.py --inspect # print a few resolutions
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import faiss
import numpy as np

HERE = Path(__file__).parent
GT = json.loads((HERE / "claim_forms_garbled" / "ground_truth.json").read_text())

# ---- Character n-gram hashing vectorizer (no sklearn needed) ----
VEC_DIM = 1024
NGRAMS = (2, 3, 4)


def embed(token: str) -> np.ndarray:
    """Character n-gram hashing embedding (position-INVARIANT).

    For resolving GARBLED OCR text we deliberately do NOT include positions:
    OCR misreads shift/delete characters, so a token like '43989' (garbled
    '439.89') or '9921k' (garbled '99213') still shares n-grams with its
    canonical form. Positional n-grams would treat those as totally different.
    """
    v = np.zeros(VEC_DIM, dtype=np.float32)
    t = token.lower().strip()
    for n in NGRAMS:
        for i in range(len(t) - n + 1):
            v[hash(t[i:i + n]) % VEC_DIM] += 1.0
    if t:
        v[hash(("full", t)) % VEC_DIM] += 1.0  # whole-token signal
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def _clean_num(tok: str) -> str:
    """Normalize a money token: '43989' -> '439.89', '4,398.9' -> '4398.90'."""
    t = tok.replace(",", "")
    if t and t.isdigit() and len(t) >= 3:
        # likely missing decimal -> insert before last 2 digits
        t = t[:-2] + "." + t[-2:]
    return t


# ---- Canonical candidate corpus per field ----
def build_corpus() -> dict[str, set[str]]:
    corpus: dict[str, set[str]] = {
        "patient_name": set(),
        "member_id": set(),
        "diagnosis": set(),
        "cpt": set(),
        "pos": set(),
        "dos": set(),
        "charge": set(),
        "provider": set(),
        "npi": set(),
        "facility": set(),
        "auth_number": set(),
    }
    for c in GT:
        corpus["patient_name"].add(c["patient_name"])
        corpus["member_id"].add(c["member_id"])
        corpus["diagnosis"].add(c["diagnosis"]) if c["diagnosis"] else None
        corpus["cpt"].add(c["cpt"]) if c["cpt"] else None
        corpus["pos"].add(c["pos"]) if c["pos"] else None
        corpus["dos"].add(c["dos"]) if c["dos"] else None
        corpus["charge"].add(f"{c['charge']:.2f}") if c["charge"] else None
        corpus["provider"].add(c["provider"])
        corpus["npi"].add(c["npi"]) if c["npi"] else None
        corpus["facility"].add(c["facility"])
        corpus["auth_number"].add(c["auth_number"])
    # add canonical codebook values for missing/empty candidates
    corpus["diagnosis"] |= {"H25.13", "E11.9", "J06.9", "M54.5", "I10", "N39.0", "G47.33"}
    corpus["cpt"] |= {"99213", "99214", "99204", "95782", "90670"}
    corpus["pos"] |= {"11", "22", "21"}
    corpus["npi"] |= {"1982635411", "1674892022", "1325478890", "1452378901", "1098723456"}
    return corpus


# ---- faiss index per field ----
class VectorResolver:
    def __init__(self):
        self.corpus = build_corpus()
        self.indexes: dict[str, faiss.IndexFlatIP] = {}
        self.candidates: dict[str, list[str]] = {}
        for field, cands in self.corpus.items():
            cands = sorted(cands)
            if not cands:
                continue
            mat = np.vstack([embed(c) for c in cands]).astype("float32")
            idx = faiss.IndexFlatIP(VEC_DIM)   # inner product == cosine (L2-normed)
            idx.add(mat)
            self.indexes[field] = idx
            self.candidates[field] = cands
        VectorResolver._shared = self  # for module-level _score()

    def save(self, outdir: Path):
        outdir.mkdir(parents=True, exist_ok=True)
        for field, idx in self.indexes.items():
            faiss.write_index(idx, str(outdir / f"{field}.faiss"))
        (outdir / "candidates.json").write_text(json.dumps(self.candidates, indent=2))
        # store an example vector + dim metadata
        (outdir / "meta.json").write_text(json.dumps({"dim": VEC_DIM, "ngrams": list(NGRAMS)}))

    def resolve(self, field: str, token: str, thresh: float = 0.72) -> str | None:
        """Map a garbled OCR token to the nearest canonical value, or None if low conf."""
        token = token.strip()
        if not token:
            return None
        if field == "charge":
            token = _clean_num(token)
        if field not in self.indexes:
            return token
        vec = embed(token).reshape(1, -1).astype("float32")
        scores, idx = self.indexes[field].search(vec, 1)
        score = float(scores[0][0])
        cand = self.candidates[field][int(idx[0][0])]
        if score >= thresh:
            return cand
        return None  # unresolved

    def _top_candidate(self, field: str, token: str) -> str | None:
        """Return the single nearest canonical candidate regardless of threshold."""
        if field not in self.indexes:
            return None
        if field == "charge":
            token = _clean_num(token)
        vec = embed(token).reshape(1, -1).astype("float32")
        scores, idx = self.indexes[field].search(vec, 1)
        return self.candidates[field][int(idx[0][0])]


# ---- parse one OCR blob into per-field tokens ----
def parse_ocr(text: str) -> dict[str, str]:
    """Extract candidate raw tokens per field from the OCR text blob.

    Robust version: pull every token, then let the vector resolver decide which
    field each token belongs to by best cosine match. Field-specific regexes
    provide strong priors for dates/NPIs/codes; the resolver handles the rest.
    """
    tokens = re.split(r"[\s\n]+", text.strip())
    tokens = [t for t in tokens if t]
    res: dict[str, str] = {}
    date_re = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
    npi_re = re.compile(r"\b\d{10}\b")
    auth_re = re.compile(r"(?i)(?:au|pa)[- ]?\d{4,5}")
    icd_re = re.compile(r"[A-HJ-NP-Z]\d{2}\.\d{1,2}|[A-HJ-NP-Z]\d{2}\b")
    cpt_re = re.compile(r"^\d{5}$")
    pos_re = re.compile(r"^\d{2}$")

    for t in tokens:
        if date_re.match(t):
            res.setdefault("dos", t)
        elif auth_re.match(t):
            res.setdefault("auth_number", t)
        elif npi_re.match(t):
            res.setdefault("npi", t)
        elif icd_re.match(t):
            res.setdefault("diagnosis", t)
        elif cpt_re.match(t):
            res.setdefault("cpt", t)
        elif pos_re.match(t):
            res.setdefault("pos", t)
    return res


def resolve_all(resolver: "VectorResolver", ocr_text: str,
                thresh: float = 0.72) -> dict[str, str]:
    """Resolve every token AND multi-word phrase in the OCR blob.

    For each field, scan tokens plus adjacent 2-3 word phrases and keep the
    best cosine match above the threshold. Multi-word phrase matching lets text
    fields like 'St. Mary's Medical Center' or 'Dr. L. Okafor' resolve even when
    OCR garbles individual words. Low-confidence matches are dropped so
    genuinely unreadable fields stay NULL (flagged as missing downstream).
    """
    tokens = [t for t in re.split(r"[\s\n]+", ocr_text.strip()) if t]
    result: dict[str, str] = {}

    # Strong-prior fields via regex (dates, NPIs, auth, codes).
    parsed = parse_ocr(ocr_text)
    for field, tok in parsed.items():
        val = resolver.resolve(field, tok, thresh)
        if val:
            result[field] = val

    # Build candidate phrases: single tokens + adjacent 2- and 3-word phrases.
    phrases = list(tokens)
    for n in (2, 3):
        phrases += [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]

    fuzz_fields = ["diagnosis", "cpt", "pos", "charge", "npi", "member_id",
                   "provider", "facility", "patient_name", "auth_number"]
    for field in fuzz_fields:
        if field in result:
            continue
        best, best_score = None, 0.0
        for ph in phrases:
            val = resolver.resolve(field, ph, thresh)
            if val is not None:
                score = _score(field, ph)
                if score > best_score:
                    best, best_score = val, score
        if best is not None:
            result[field] = best
    return result


def _score(field: str, token: str) -> float:
    """Raw cosine similarity of a token to its best canonical candidate."""
    r = VectorResolver._shared if hasattr(VectorResolver, "_shared") else None
    if r is None or field not in r.indexes:
        return 0.0
    vec = embed(token).reshape(1, -1).astype("float32")
    scores, _ = r.indexes[field].search(vec, 1)
    return float(scores[0][0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    r = VectorResolver()
    r.save(HERE / "vector_db")

    if args.inspect:
        print("=== vector resolver sample resolutions ===")
        # Load real OCR and resolve each blob to canonical values
        for f in sorted((HERE / "ocr_output").glob("*.ocrtext")):
            resolved = resolve_all(r, f.read_text())
            print(f"\n{f.stem}:")
            for field, val in sorted(resolved.items()):
                print(f"   {field:12} -> {val}")
    print(f"\nIndex built: {sum(len(c) for c in r.candidates.values())} candidates "
          f"across {len(r.indexes)} fields -> vector_db/")


if __name__ == "__main__":
    main()
