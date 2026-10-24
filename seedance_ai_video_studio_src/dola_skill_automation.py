"""Install and select the supplied Dola video skill through native controls.

The markdown is a Dola asset, not instructions for this Python application.
No chat request rewrites, hidden model overrides, or claimed generation success.
"""
import asyncio
import hashlib
import json
import re
import time
import threading
import uuid
from pathlib import Path

SKILL_FILE = Path(__file__).parent / 'assets' / 'video_30s' / 'SKILL.md'
SKILL_NAME = 'MianBrothers-seedance-2-5-30s'
SKILL_LABEL = re.compile(r'^Mianbrothers[ _-]+Seedance[ _-]+2[ _-]+5[ _-]+30s$', re.I)
SKILL_CARD_LABEL = re.compile(r'^Mianbrothers\s+Seedan', re.I)
_status_lock = threading.Lock()


def skill_metadata(path=SKILL_FILE):
    content = Path(path).read_text(encoding='utf-8-sig')
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.S)
    if not match:
        raise ValueError('SKILL.md thiếu YAML frontmatter.')
    name = re.search(r'^name:\s*(.+)$', match[1], re.M)
    description = re.search(r'^description:\s*(.+)$', match[1], re.M)
    if not name or not description:
        raise ValueError('SKILL.md phải có name và description.')
    return {'name': name[1].strip().strip('"\''),
            'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()}


async def dismiss_consent(page):
    button = page.get_by_role('button', name=re.compile(r'^(OK|Accept all|Chấp nhận tất cả)$'))
    if await button.count() and await button.first.is_visible():
        try:
            await button.first.click(timeout=3000, no_wait_after=True)
        except Exception:
            # The click may already have dismissed the banner and navigated
            # the SPA before Playwright's navigation wait timed out.
            try:
                if await button.count() and await button.first.is_visible():
                    await button.first.evaluate('(el) => el.click()')
            except Exception:
                pass


async def open_skills(page):
    """Enter through the SPA sidebar; a cold /skills load can show an error page."""
    await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=30000)
    entry = page.get_by_text(re.compile(r'^(Kỹ năng|Skills)$'))
    await entry.first.wait_for(state='visible', timeout=20000)
    await dismiss_consent(page)
    await entry.first.click(timeout=10000)
    await page.get_by_role('button', name=re.compile(r'^(Quản lý|Manage)$')).wait_for(
        state='visible', timeout=20000)


class DolaSkillAutomation:
    def __init__(self, cancelled=lambda: False):
        self.cancelled = cancelled

    def check_cancel(self):
        if self.cancelled():
            raise asyncio.CancelledError()

    async def ensure_installed(self, page, account_name='', progress=None):
        notify = progress or (lambda message: None)
        metadata = skill_metadata()
        self.check_cancel()
        from fb_login_automation import FBLoginAutomation
        # This tool's FBLoginAutomation exposes a page-level Dola session
        # check, not fetch_dola_account_info(context). Use the implemented
        # check against the injected account's live page.
        if not await FBLoginAutomation()._check_dola_logged_in(page):
            raise RuntimeError('SKILL_AUTH_REQUIRED: phiên Dola không hợp lệ; đăng nhập lại tài khoản.')
        metadata['account_name'] = account_name
        # Reuse a recent live verification for this same Skill file/account;
        # the subsequent activation still verifies the native editor token.
        if account_name:
            try:
                from config import DATA_DIR
                status_file = Path(DATA_DIR) / 'dola_skill_status.json'
                saved = json.loads(status_file.read_text(encoding='utf-8')).get(account_name, {})
                age = time.time() - float(saved.get('checked_at', 0))
                if (saved.get('sha256') == metadata['sha256']
                        and saved.get('status') in ('installed', 'already_installed')
                        and 0 <= age < 3600):
                    notify('Skill 30s đã được xác minh gần đây cho account này.')
                    return {**metadata, 'status': saved['status']}
            except (OSError, ValueError, TypeError):
                pass
        await open_skills(page)
        manage = page.get_by_role('button', name=re.compile(r'^(Quản lý|Manage)$'))
        await manage.wait_for(state='visible', timeout=20000)
        await asyncio.sleep(2)
        await dismiss_consent(page)
        try:
            await manage.click(timeout=3000, no_wait_after=True)
        except Exception:
            pass
        # Manage cards visually truncate the full title to "Mianbrothers
        # Seedan..." in the current Dola UI; match the stable prefix there.
        installed = page.get_by_text(SKILL_CARD_LABEL)
        for _ in range(20):
            if await installed.count() and await installed.first.is_visible():
                notify('Skill 30s đã có trong danh sách quản lý của tài khoản.')
                return {**metadata, 'status': 'already_installed'}
            await asyncio.sleep(0.5)

        # Return from Manage before opening the upload menu.
        await open_skills(page)
        add = page.get_by_role('button', name=re.compile(r'^(Thêm|Add)$'))
        await add.wait_for(timeout=20000)
        await asyncio.sleep(2)
        await dismiss_consent(page)
        try:
            await add.click(timeout=3000, no_wait_after=True)
        except Exception:
            pass
        await page.get_by_text(re.compile(r'^(Tải kỹ năng lên|Upload skill)$')).click(timeout=5000)
        await page.locator('input[type="file"][accept*=".md"]').set_input_files(str(SKILL_FILE.resolve()))
        notify('Đã tải SKILL.md lên Dola; chờ kiểm tra và xác nhận cài đặt...')
        deadline = time.monotonic() + 90
        clicked_install = False
        while time.monotonic() < deadline:
            self.check_cancel()
            body = await page.locator('body').inner_text()
            if re.search(r'Skill uploaded|Kỹ năng đã được tải lên|Đã tải kỹ năng|tải lên thành công', body, re.I):
                break
            dialog = page.get_by_role('dialog')
            scope = dialog.last if await dialog.count() else page
            install = scope.get_by_role('button', name=re.compile(r'^(Cài đặt|Install|Thêm|Add|Xác nhận|Confirm|Tải lên|Upload)$'))
            if not clicked_install and await install.count() and await install.last.is_visible() and await install.last.is_enabled():
                await install.last.click(timeout=5000)
                clicked_install = True
            elif clicked_install and not await dialog.count():
                break
            if re.search(r'invalid skill|không hợp lệ|upload failed|tải lên thất bại', body, re.I):
                raise RuntimeError('SKILL_INSTALL_FAILED: Dola từ chối file skill.')
            await asyncio.sleep(1)

        # A preview or success toast alone is not installation proof.
        await open_skills(page)
        await manage.wait_for(timeout=20000)
        await asyncio.sleep(2)
        await dismiss_consent(page)
        await manage.click(timeout=5000)
        await page.get_by_text(SKILL_LABEL).first.wait_for(state='visible', timeout=15000)
        notify('Đã xác minh Skill 30s trong danh sách quản lý Dola.')
        return {**metadata, 'status': 'installed'}

    async def activate(self, page):
        """Open the installed skill's native 'Try in new chat' action."""
        self.check_cancel()
        if '/skills' not in page.url:
            await open_skills(page)
            await asyncio.sleep(2)
            await dismiss_consent(page)
            manage = page.get_by_role('button', name=re.compile(r'^(Quản lý|Manage)$'))
            if await manage.count() and await manage.is_visible():
                try:
                    await manage.click(timeout=3000, no_wait_after=True)
                except Exception:
                    pass
        item = page.get_by_text(SKILL_CARD_LABEL).first
        await item.wait_for(state='visible', timeout=20000)
        try:
            # The tool's floating extension pill may cover the row's center.
            # Trigger the row's own native click handler instead of relying on
            # pointer coordinates, then confirm the resulting editor state.
            await item.evaluate('(el) => el.click()')
        except Exception:
            pass
        editor = page.locator('[contenteditable="true"]').first
        for _ in range(60):
            clean_url = page.url.split('?', 1)[0]
            if '/chat' in clean_url and '/skills' not in clean_url:
                try:
                    if await editor.is_visible():
                        return editor
                except Exception:
                    pass
            await asyncio.sleep(0.5)
        # Older Dola builds show an explicit action in the skill details pane.
        launch = page.get_by_role('button', name=re.compile(r'^(Thử trong cuộc trò chuyện mới|Try in new chat)$'))
        await launch.click(timeout=10000, force=True, no_wait_after=True)
        await editor.wait_for(state='visible', timeout=15000)
        return editor


def record_skill_status(account_name, result):
    """Diagnostic cache only. Each run still checks the server's skill list."""
    from config import DATA_DIR
    path = Path(DATA_DIR) / 'dola_skill_status.json'
    with _status_lock:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        data[account_name] = {**result, 'checked_at': time.time()}
        temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
