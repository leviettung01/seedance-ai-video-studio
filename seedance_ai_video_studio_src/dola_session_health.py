"""Restore saved sessions without overwriting a newer live browser login."""

async def restore_account_session(page, store, account_name, notify=lambda message: None,
                                  checker=None):
    if checker is None:
        from fb_login_automation import FBLoginAutomation
        checker = FBLoginAutomation()
    if await checker._check_dola_logged_in(page):
        cookies, storage = await store.extract_from_browser(page.context, page)
        store.save_session(account_name, cookies, storage)
        notify('Giữ phiên Dola đang hoạt động; đã cập nhật bản lưu của tool.')
        return True
    if not store.has_session(account_name):
        return False
    if not await store.inject_to_browser(page.context, page, account_name):
        return False
    await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=30000)
    valid = await checker._check_dola_logged_in(page)
    notify('Đã xác thực phiên Dola.' if valid else 'Phiên lưu không đăng nhập được; cần đăng nhập lại trong Chrome này.')
    return valid
