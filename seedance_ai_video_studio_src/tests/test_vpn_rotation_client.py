import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from vpn_rotation_client import selected_ports


class ScopeTests(unittest.TestCase):
    def test_only_selected_local_vpn_ports_are_registered(self):
        data = {'enabled': True, 'source': 'vpn_tool', 'proxies': [
            '127.0.0.1:10000:user:pass', 'http://user:pass@localhost:10001',
            '127.0.0.1:10000', 'https://example.com:10002', 'not-a-proxy',
            '127.0.0.1:70000']}
        self.assertEqual(selected_ports(data), [10000, 10001])

    def test_disabled_custom_or_opt_out_do_not_rotate(self):
        base = {'enabled': True, 'source': 'vpn_tool', 'proxies': ['127.0.0.1:10000']}
        for change in ({'enabled': False}, {'source': 'custom'}, {'vpn_auto_rotate': False}):
            self.assertEqual(selected_ports(dict(base, **change)), [])

    def test_custom_pool_is_never_used_as_vpn_fallback(self):
        self.assertEqual(selected_ports({'source': 'vpn_tool', 'proxies': [],
                                         'custom_proxies': ['127.0.0.1:10000']}), [])


if __name__ == '__main__':
    unittest.main()
