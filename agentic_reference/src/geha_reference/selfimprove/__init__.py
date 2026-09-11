"""Self-improving loop package for the 35-category classification task."""

from .categories import CATEGORIES, category_names
from .classifier import OverfitClassifier
from .data import Example, ExampleGenerator
from .loop import IterResult, run_loop
from .metrics import evaluate
from .probe import ProbeAgent

__all__ = [
    "CATEGORIES",
    "category_names",
    "OverfitClassifier",
    "Example",
    "ExampleGenerator",
    "IterResult",
    "run_loop",
    "evaluate",
    "ProbeAgent",
]
