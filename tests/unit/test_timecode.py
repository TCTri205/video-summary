from __future__ import annotations

import unittest

from reasoning_nlp.common.timecode import ms_to_timestamp, seconds_to_timestamp, to_ms


class TimecodeTests(unittest.TestCase):
    def test_roundtrip_ms(self) -> None:
        value = 3_726_045
        ts = ms_to_timestamp(value)
        self.assertEqual(ts, "01:02:06.045")
        self.assertEqual(to_ms(ts), value)

    def test_seconds_to_timestamp_rounding(self) -> None:
        self.assertEqual(seconds_to_timestamp(1.2346), "00:00:01.235")

    def test_invalid_timestamp_raises(self) -> None:
        with self.assertRaises(ValueError):
            to_ms("1:2:3.4")


if __name__ == "__main__":
    unittest.main()
