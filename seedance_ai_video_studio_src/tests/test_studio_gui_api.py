import pathlib
import sys
import unittest
from unittest.mock import Mock, patch
import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import api_server


class GuiCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_command_is_dispatched_to_gui(self):
        manager = Mock()
        manager.get_account.return_value = object()
        received = []
        transport = httpx.ASGITransport(app=api_server.app, client=('127.0.0.1', 12345))
        with patch.object(api_server, 'account_manager', manager), \
             patch.object(api_server, 'gui_open_accounts_handler', received.append):
            async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:8899') as client:
                response = await client.post('/api/studio/open-accounts', json={'accounts': ['a', 'a', 'b']})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(received, [['a', 'b']])

    async def test_web_origin_cannot_open_saved_accounts(self):
        received = []
        transport = httpx.ASGITransport(app=api_server.app, client=('127.0.0.1', 12345))
        with patch.object(api_server, 'gui_open_accounts_handler', received.append):
            async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:8899') as client:
                response = await client.post('/api/studio/open-accounts', json={'accounts': ['a']},
                                             headers={'Origin': 'https://untrusted.example'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(received, [])
