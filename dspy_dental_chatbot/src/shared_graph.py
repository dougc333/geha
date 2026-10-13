"""Load the proven policy graph from the sibling dental chatbot project."""

from __future__ import annotations

import sys
from pathlib import Path


ORIGINAL_SRC = Path(__file__).resolve().parents[2] / "dental_enrollment_chatbot" / "src"
if str(ORIGINAL_SRC) not in sys.path:
    sys.path.insert(0, str(ORIGINAL_SRC))

from enrollment_graph import DentalEnrollmentGraph  # noqa: E402

__all__ = ["DentalEnrollmentGraph", "ORIGINAL_SRC"]

