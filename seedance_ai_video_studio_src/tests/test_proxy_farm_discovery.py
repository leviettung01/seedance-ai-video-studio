import unittest
import pathlib
import sys
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import proxy_manager


class FarmDiscoveryTests(unittest.TestCase):
    def discover(self, rows):
        client = MagicMock()
        client.__enter__.return_value.get.return_value.json.return_value = {
            'rows': rows, 'auth': {'user': 'test-user', 'pass': 'test-secret'}}
        with patch.object(proxy_manager.httpx, 'Client', return_value=client), \
             patch.object(proxy_manager.socket, 'create_connection'):
            return proxy_manager.import_from_proxy_farm()

    def test_rejects_listening_but_unhealthy_tunnel(self):
        self.assertEqual(self.discover([
            {'port': 29001, 'state': 'running', 'ok': False, 'ip': '203.0.113.1'},
            {'port': 29002, 'state': 'stopped', 'ok': True, 'ip': '203.0.113.2'},
            {'port': 29003, 'state': 'running', 'ok': True}]), [])

    def test_healthy_tunnel_maps_credentials_and_source(self):
        result = self.discover([{'key': 'FR-TEST', 'port': 29001, 'state': 'running',
                                'ok': True, 'ip': '203.0.113.1', 'country': 'FR'}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source'], 'proxy-farm')
        self.assertEqual(result[0]['auth_user'], 'test-user')
        self.assertEqual(result[0]['country_code'], 'FR')

    def test_farm_discovery_does_not_require_legacy_db(self):
        with patch.object(proxy_manager, 'import_from_proxy_farm', return_value=[{'port': 29001}]), \
             patch.object(proxy_manager, 'find_ocproxy_db_path', return_value=None):
            self.assertEqual(proxy_manager.import_from_ocproxy_hub(), [{'port': 29001}])

    def test_per_port_auth_overrides_shared_farm_auth(self):
        rows = self.discover([{'key': 'FR-TEST', 'port': 10000, 'state': 'running',
                              'ok': True, 'ip': '203.0.113.1',
                              'auth': {'user': 'port-user', 'pass': 'port-secret'}}])
        self.assertEqual(rows[0]['auth_user'], 'port-user')
