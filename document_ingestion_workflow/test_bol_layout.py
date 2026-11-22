import unittest

from .backend import DEMO_DOCUMENTS
from .bill_of_lading_workflow import (
    BILL_OF_LADING_LAYOUTS,
    _active_layout,
    use_bill_of_lading_layout,
)


class BillOfLadingLayoutTests(unittest.TestCase):
    def test_layout_context_sets_and_restores_active_layout(self):
        default = _active_layout.get()
        with use_bill_of_lading_layout(BILL_OF_LADING_LAYOUTS[1]):
            self.assertEqual(_active_layout.get(), BILL_OF_LADING_LAYOUTS[1])
        self.assertEqual(_active_layout.get(), default)

    def test_unknown_layout_is_rejected(self):
        with self.assertRaises(ValueError):
            with use_bill_of_lading_layout("nope.py"):
                pass

    def test_alt_2_document_is_registered_with_its_workflow(self):
        config = DEMO_DOCUMENTS["forms/bill_of_lading_alt_2.pdf"]
        self.assertEqual(config["workflow"], "bill_of_lading_alt_2")


if __name__ == "__main__":
    unittest.main()
