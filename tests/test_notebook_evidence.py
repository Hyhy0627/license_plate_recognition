"""Evidence errors must not turn into successful notebook conclusions."""
import unittest
from unittest.mock import patch

from notebooks._support import assert_equivalent, compare_regressions, regression_frame


class NotebookEvidenceTests(unittest.TestCase):
    def test_rejects_edited_metric_summary(self):
        with self.assertRaisesRegex(ValueError, "value differs"):
            assert_equivalent({"ap50": 0.952}, {"ap50": 0.02})
        assert_equivalent({"cer": None, "count": 0}, {"cer": None, "count": 0})

    def frame(self, expected, actual, status=200):
        frozen = {"id": "fixture", "sha256": "abc", "kind": "synthetic", "expected": expected}
        run = {"cases": [{**frozen, "http_status": status, "wall_ms": 1,
                          "response": {"success": status == 200,
                                       "results": [{"plate_number": p} for p in actual]}}]}
        with patch("notebooks._support.read_json", return_value=run), patch(
                "notebooks._support.load_development_cases", return_value=[frozen]):
            return regression_frame("run.json", "cases.json")[1]

    def test_missing_duplicate_and_wrong_grouping_fail(self):
        self.assertFalse(self.frame(["29A-123.45"] * 2, ["29A-123.45"]).iloc[0].exact)
        self.assertFalse(self.frame(["54-H4 5555"], ["54H-455.55"]).iloc[0].exact)
        self.assertTrue(self.frame(["29-MD1 001.60"], ["29MD1 00160"]).iloc[0].exact)

    def test_negative_http_error_is_not_a_correct_rejection(self):
        self.assertFalse(self.frame([], [], status=500).iloc[0].exact)
        self.assertTrue(self.frame([], []).iloc[0].exact)

    def test_comparison_rejects_changed_truth_and_mixed_protocols(self):
        before = self.frame(["29A-123.45"], ["29A-123.45"])
        after = self.frame(["29A-123.46"], ["29A-123.46"])
        with self.assertRaisesRegex(ValueError, "changed expected"):
            compare_regressions({"mode": "local"}, before, {"mode": "local"}, after)
        with self.assertRaisesRegex(ValueError, "different protocols"):
            compare_regressions({"mode": "local"}, before, {"mode": "Brave UI upload"}, before)


if __name__ == "__main__":
    unittest.main()
