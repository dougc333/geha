import unittest

from context_assembly_benchmarks.chunking_compare import fact_present, normalized


class DrugNameNormalizationTests(unittest.TestCase):
    def test_curated_drug_alias_repairs_internal_space(self):
        extracted = "Pembrolizumab and berahyaluronidas e alfa-pmph (Keytruda QLEX)"
        generated = "Pembrolizumab and berahyaluronidase alfa-pmph (Keytruda QLEX)"

        self.assertEqual(normalized(extracted), normalized(generated))
        self.assertTrue(fact_present({"match": [extracted]}, generated))

    def test_drug_alias_normalization_does_not_change_hcpcs_codes(self):
        self.assertEqual(normalized("Keytruda QLEX — J9277"), "keytruda qlex j9277")
