import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, Mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fb_login_automation import FBLoginAutomation


class LoginRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_probe_uses_browser_fetch_and_never_the_direct_request_client(self):
        page = Mock(url='https://www.dola.com/chat/')
        page.evaluate = AsyncMock(return_value={'message': 'success', 'data': {'user_id': 'test', 'is_visitor_account': False}})
        context = Mock(pages=[page])
        context.request.get = AsyncMock()
        self.assertIsNotNone(await FBLoginAutomation().fetch_dola_account_info(context))
        page.evaluate.assert_awaited_once()
        context.request.get.assert_not_called()

    async def test_missing_dola_page_never_sends_credentials_directly(self):
        context = Mock(pages=[Mock(url='https://example.com/')])
        context.request.get = AsyncMock()
        self.assertIsNone(await FBLoginAutomation().fetch_dola_account_info(context))
        context.request.get.assert_not_called()
