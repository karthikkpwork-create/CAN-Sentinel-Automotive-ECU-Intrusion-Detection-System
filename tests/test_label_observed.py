import unittest

from src.utils.label_observed import label_rows


def S(cid, p, label, atype, status="transmitted"):
    return {"can_id": str(cid), "payload_hex": p, "label": str(label), "attack_type": atype, "status": status}


def O(cid, p):
    return {"can_id": str(cid), "payload_hex": p}


class LabelObservedTests(unittest.TestCase):
    def test_matched_frames_inherit_labels(self):
        sent = [S(256, "AA", 0, "normal"), S(256, "AA", 1, "injection")]
        rows, missing = label_rows(sent, [O(256, "aa"), O(256, "AA")])
        self.assertEqual([r["attack_type"] for r in rows], ["normal", "injection"])
        self.assertEqual(missing, 0)

    def test_unmatched_observed_is_attack(self):
        rows, _ = label_rows([], [O(2047, "00")])
        self.assertEqual((rows[0]["label"], rows[0]["attack_type"]), ("1", "unmatched"))

    def test_unobserved_and_failed_sends(self):
        sent = [S(1, "01", 0, "normal"), S(1, "02", 0, "normal", status="failed:ENOBUFS")]
        rows, missing = label_rows(sent, [])
        self.assertEqual(rows, [])
        self.assertEqual(missing, 1)


if __name__ == "__main__":
    unittest.main()
