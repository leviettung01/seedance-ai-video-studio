import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import vpn_bootstrap


class BootstrapTests(unittest.TestCase):
    def test_running_hub_never_launches_a_second_instance(self):
        with patch.object(vpn_bootstrap, 'hub_ready', return_value=True), \
             patch.object(vpn_bootstrap.subprocess, 'Popen') as start:
            vpn_bootstrap.ensure_vpn_hub()
            start.assert_not_called()

    def test_missing_launcher_fails_before_starting_or_falling_back(self):
        with patch.object(vpn_bootstrap, 'hub_ready', return_value=False), \
             patch.object(vpn_bootstrap.pathlib.Path, 'is_file', return_value=False), \
             patch.object(vpn_bootstrap.subprocess, 'Popen') as start:
            with self.assertRaises(RuntimeError): vpn_bootstrap.ensure_vpn_hub(wait_seconds=0)
            start.assert_not_called()

    def test_failed_start_returns_error_without_using_direct_network(self):
        with patch.object(vpn_bootstrap, 'hub_ready', return_value=False), \
             patch.object(vpn_bootstrap.pathlib.Path, 'is_file', return_value=True), \
             patch.object(vpn_bootstrap.subprocess, 'Popen') as start:
            with self.assertRaisesRegex(RuntimeError, 'Không dùng mạng trực tiếp'):
                vpn_bootstrap.ensure_vpn_hub(wait_seconds=0)
            start.assert_called_once()
