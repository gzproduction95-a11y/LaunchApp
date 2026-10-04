import unittest

from PythonApps.Launch.input_events import encode_input_event
from RemoteScripts.Launch.input_events import decode_input_event, extend_device_millis


class V2InputEventsTests(unittest.TestCase):
    def test_raw_fn_press_release_and_pad_hold_keep_original_timestamp(self):
        payload = encode_input_event(0x12345, 41, 987654, True,
                                     pressed=True, released=False, held=False,
                                     x=None, y=None)
        event = decode_input_event(payload)
        self.assertEqual(event, {
            "session_id": 0x12345, "event_id": 41, "device_ms": 987654,
            "is_function": True, "pressed": True, "released": False,
            "held": False, "x": None, "y": None,
        })
        pad_payload = encode_input_event(0x12345, 42, 987700, False,
                                         pressed=False, released=False, held=True,
                                         x=7, y=1)
        self.assertTrue(decode_input_event(pad_payload)["held"])
        self.assertEqual((decode_input_event(pad_payload)["x"],
                          decode_input_event(pad_payload)["y"]), (7, 1))

    def test_invalid_coordinates_and_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            encode_input_event(1, 1, 1, False, True, False, False, 8, 0)
        self.assertIsNone(decode_input_event((0,) * 13))

    def test_device_timestamp_unwraps_across_28_bit_rollover(self):
        self.assertEqual(extend_device_millis(0x0FFFFFF0, None, None),
                         (0x0FFFFFF0, 0x0FFFFFF0))
        wrapped, absolute = extend_device_millis(20, 0x0FFFFFF0, 0x0FFFFFF0)
        self.assertEqual(wrapped, 20)
        self.assertEqual(absolute, 0x10000014)

    def test_old_or_ambiguous_timestamp_is_rejected(self):
        self.assertIsNone(extend_device_millis(4, 10, 100))
        self.assertIsNone(extend_device_millis(0x08000010, 10, 100))


if __name__ == "__main__":
    unittest.main()
