import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from dola_session_health import restore_account_session


class SessionRestoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_login_is_saved_without_stale_cookie_injection(self):
        page = Mock(context=object())
        store = Mock()
        store.extract_from_browser = AsyncMock(return_value=(['live-cookie'], {'live': 'state'}))
        store.inject_to_browser = AsyncMock()
        checker = Mock(_check_dola_logged_in=AsyncMock(return_value=True))
        self.assertTrue(await restore_account_session(page, store, 'account', checker=checker))
        store.inject_to_browser.assert_not_called()
        store.save_session.assert_called_once_with('account', ['live-cookie'], {'live': 'state'})

    async def test_cookie_injection_alone_does_not_count_as_login(self):
        page = Mock(context=object(), goto=AsyncMock())
        store = Mock(has_session=Mock(return_value=True), inject_to_browser=AsyncMock(return_value=True))
        checker = Mock(_check_dola_logged_in=AsyncMock(side_effect=[False, False]))
        self.assertFalse(await restore_account_session(page, store, 'account', checker=checker))
        store.save_session.assert_not_called()

    async def test_valid_restored_session_is_accepted(self):
        page = Mock(context=object(), goto=AsyncMock())
        store = Mock(has_session=Mock(return_value=True), inject_to_browser=AsyncMock(return_value=True))
        checker = Mock(_check_dola_logged_in=AsyncMock(side_effect=[False, True]))
        self.assertTrue(await restore_account_session(page, store, 'account', checker=checker))
