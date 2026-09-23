"""Contract checks for an oracle that must not hide a missing/reordered event."""
import unittest
from copy import deepcopy
from compare_receiver import compare


def event(index, time_ns, stage, signal):
    return dict(event_index=str(index), time_ns=str(time_ns), stage=stage,
                signal_id=str(signal), source="8", hop_sequence="174", result="",
                reason="", state_before="Search", state_after="Track")


class ComparisonContract(unittest.TestCase):
    def setUp(self):
        self.reference = [event(1, 10, "signal_start", 1), event(2, 10, "track", 1),
                          event(3, 20, "signal_end", 1)]

    def test_raw_reason_diagnostic_does_not_mask_decision(self):
        candidate = deepcopy(self.reference)
        candidate[-1]["raw_reason"] = "not_acquired"
        self.assertTrue(compare(self.reference, candidate, 0, 30)["passed"])
        candidate[-1]["result"] = "accepted"
        result = compare(self.reference, candidate, 0, 30)
        self.assertEqual(result["first_difference"]["category"], "receiver_decision")

    def test_equal_time_reorder_fails(self):
        candidate = [self.reference[1], self.reference[0], self.reference[2]]
        result = compare(self.reference, candidate, 0, 30)
        self.assertFalse(result["passed"])
        self.assertEqual(result["matching_prefix_events"], 0)

    def test_missing_terminal_event_fails(self):
        result = compare(self.reference, self.reference[:-1], 0, 30)
        self.assertEqual(result["first_difference"]["category"], "missing_or_extra_event")

    def test_nanosecond_change_is_visible_by_default(self):
        candidate = deepcopy(self.reference)
        candidate[-1]["time_ns"] = "21"
        self.assertFalse(compare(self.reference, candidate, 0, 30)["passed"])
        self.assertTrue(compare(self.reference, candidate, 0, 30, 1)["passed"])

    def test_empty_reference_cannot_pass(self):
        with self.assertRaises(ValueError):
            compare(self.reference, self.reference, 40, 50)


if __name__ == "__main__":
    unittest.main()
