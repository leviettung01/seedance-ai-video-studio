import pathlib
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import browser_capacity as capacity


class CapacityTests(unittest.TestCase):
    def test_pending_launch_counts_towards_ten_browser_limit(self):
        with patch.object(capacity, '_observed', set(range(1, 10))), \
             patch.object(capacity, '_started', set()), \
             patch.object(capacity, '_pending', set()), \
             patch.object(capacity, '_checked_at', time.monotonic()), \
             patch.object(capacity.psutil, 'pid_exists', return_value=True):
            capacity.reserve_browser('tenth')
            with self.assertRaisesRegex(RuntimeError, '10 Chrome'):
                capacity.reserve_browser('eleventh')
            capacity.release_reservation('tenth')
            capacity.reserve_browser('replacement')
