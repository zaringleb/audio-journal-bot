from datetime import datetime, timezone

import unittest

from src.date_utils import journal_date


class JournalDateTests(unittest.TestCase):
    def test_before_cutoff_returns_previous_day(self):
        # 02:30 UTC should be 02:30 London (no DST) and map to previous day
        ts = datetime(2025, 1, 15, 2, 30, tzinfo=timezone.utc)
        self.assertEqual(journal_date(ts).isoformat(), "2025-01-14")

    def test_after_cutoff_same_day(self):
        # 05:00 UTC maps to 05:00 London, after cutoff
        ts = datetime(2025, 1, 15, 5, 0, tzinfo=timezone.utc)
        self.assertEqual(journal_date(ts).isoformat(), "2025-01-15")

    def test_dst_summer_time(self):
        # 03:00 UTC in July is 04:00 BST (UTC+1) -> equals cutoff, so still previous day
        ts = datetime(2025, 7, 21, 3, 0, tzinfo=timezone.utc)
        # At local 04:00 equals cutoff, classify as previous only if < cutoff, so expect 2025-07-21
        self.assertEqual(journal_date(ts).isoformat(), "2025-07-21")


if __name__ == "__main__":
    unittest.main() 