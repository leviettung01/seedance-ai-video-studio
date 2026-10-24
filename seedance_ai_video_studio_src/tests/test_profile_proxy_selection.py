import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from proxy_manager import ProxyManager, ProxyPool


class ProfileProxyTests(unittest.TestCase):
    def manager(self, source='vpn_tool', enabled=True):
        m = ProxyManager.__new__(ProxyManager)
        m.pool = ProxyPool()
        m.pool.enabled = enabled
        m.pool.source = source
        m.pool.proxies = ['http://new:secret@127.0.0.1:10000']
        return m

    def test_vpn_profile_replaces_stale_credentials_with_current_pool(self):
        m = self.manager()
        self.assertEqual(m.select_profile_proxy('account', 'http://old:stale@127.0.0.1:10000'), m.pool.proxies[0])

    def test_empty_vpn_pool_does_not_reuse_unselected_saved_proxy(self):
        m = self.manager()
        m.pool.proxies = []
        m.pool.custom_proxies = ['http://unselected-custom:1234']
        self.assertEqual(m.select_profile_proxy('account', 'http://old:10000'), '')

    def test_disabled_proxy_mode_has_no_profile_proxy(self):
        self.assertEqual(self.manager(enabled=False).select_profile_proxy('account', 'http://old:10000'), '')
