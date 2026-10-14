import unittest

from src.utils.can_frame import (CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_FRAME_SIZE, CAN_RTR_FLAG,
                                 format_can_id, pack_frame, unpack_frame)
import struct


class FrameTests(unittest.TestCase):
    def test_frame_size_is_16(self):
        self.assertEqual(CAN_FRAME_SIZE, 16)

    def test_roundtrip(self):
        raw = pack_frame(0x123, bytes.fromhex("DEADBEEF"))
        self.assertEqual(len(raw), 16)
        f = unpack_frame(raw)
        self.assertEqual((f.can_id, f.dlc, f.data), (0x123, 4, bytes.fromhex("DEADBEEF")))
        self.assertFalse(f.is_extended or f.is_rtr or f.is_error)

    def test_empty_payload(self):
        f = unpack_frame(pack_frame(0x7FF, b""))
        self.assertEqual((f.can_id, f.dlc, f.data), (0x7FF, 0, b""))

    def test_payload_too_long(self):
        with self.assertRaises(ValueError):
            pack_frame(0x100, bytes(9))

    def test_id_out_of_range(self):
        for bad in (-1, 0x800, "0x100", True):
            with self.assertRaises(ValueError):
                pack_frame(bad, b"")

    def test_wrong_size_rejected(self):
        with self.assertRaises(ValueError):
            unpack_frame(bytes(72))
        with self.assertRaises(ValueError):
            unpack_frame(b"\x00" * 5)

    def test_invalid_dlc_rejected(self):
        raw = struct.pack("=IB3x8s", 0x100, 12, bytes(8))
        with self.assertRaises(ValueError):
            unpack_frame(raw)

    def test_flags(self):
        ext = unpack_frame(struct.pack("=IB3x8s", CAN_EFF_FLAG | 0x1ABCDE, 1, b"\x01" + bytes(7)))
        self.assertTrue(ext.is_extended)
        self.assertEqual(ext.can_id, 0x1ABCDE)
        rtr = unpack_frame(struct.pack("=IB3x8s", CAN_RTR_FLAG | 0x100, 4, bytes(8)))
        self.assertTrue(rtr.is_rtr)
        self.assertEqual(rtr.data, b"")
        err = unpack_frame(struct.pack("=IB3x8s", CAN_ERR_FLAG | 0x4, 8, bytes(8)))
        self.assertTrue(err.is_error)

    def test_format_can_id(self):
        self.assertEqual(format_can_id(0x1), "0x001")
        self.assertEqual(format_can_id(0x1ABCDE, True), "0x001ABCDE")


if __name__ == "__main__":
    unittest.main()
