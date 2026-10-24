"""One isolated, visible Dola session using the user's saved cookies."""
import argparse
import asyncio
import json
import re
import tempfile
import time
import traceback
from pathlib import Path

from playwright.async_api import async_playwright
from config import CHROME_PATH, DATA_DIR
from proxy_manager import ProxyManager, parse_proxy_spec
from session_store import SessionStore
from fb_login_automation import FBLoginAutomation
from native_video_automation import NativeVideoAutomation


async def main(account, duration=30, model='2.5'):
    out = Path(r'D:\Seedance\output_videos') / ('dola_direct_' + time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir(parents=True, exist_ok=True)
    def report(event, **data):
        row = {'time': time.time(), 'event': event, 'account': account, **data}
        with (out / 'manifest.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=True), flush=True)

    store = SessionStore()
    if not store.has_session(account):
        raise RuntimeError('No saved session for the requested account')
    pm = ProxyManager()
    spec = parse_proxy_spec(pm.select_profile_proxy(account))
    if not spec:
        report('stopped', reason='VPN2Proxy has no configured proxy; no direct fallback')
        return
    # Chromium gets credentials through Playwright's proxy configuration,
    # never through printed command lines or a shared browser profile.
    from urllib.parse import urlsplit, unquote
    u = urlsplit(spec['url'])
    proxy = {'server': f'{u.scheme}://{u.hostname}:{u.port}'}
    if u.username:
        proxy.update(username=unquote(u.username), password=unquote(u.password or ''))
    profile = tempfile.mkdtemp(prefix='dola_direct_', dir=DATA_DIR)
    report('start', output=str(out), isolated_profile=True, proxy_endpoint=proxy['server'], profile=profile, duration=duration, model=model)
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            profile, executable_path=CHROME_PATH, headless=False,
            proxy=proxy, accept_downloads=True, downloads_path=str(out),
            viewport=None, args=['--lang=vi', '--start-maximized'])
        page = context.pages[0] if context.pages else await context.new_page()
        async def watch():
            while True:
                await asyncio.sleep(10)
                try:
                    await page.screenshot(path=str(out / 'live_state.png'), timeout=5000)
                    (out / 'live_page.txt').write_text(await page.locator('body').inner_text(timeout=5000), encoding='utf-8')
                except Exception:
                    pass
        watcher = asyncio.create_task(watch())
        try:
            # Check the actual browser route before transmitting Dola cookies.
            await page.goto('https://ipinfo.io/json', wait_until='domcontentloaded', timeout=30000)
            geo = json.loads(await page.locator('body').inner_text())
            country = geo.get('country', '')
            report('proxy_country', country=country)
            if country not in {'FR', 'TH', 'JP'}:
                raise RuntimeError('Proxy country is outside the user-approved FR/TH/JP set')
            await store.inject_to_browser(context, page, account)
            await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=45000)
            await asyncio.sleep(6)
            logged_in = await FBLoginAutomation()._check_dola_logged_in(page)
            await page.screenshot(path=str(out / 'login_state.png'))
            report('login_checked', logged_in=logged_in)
            if not logged_in:
                report('stopped', reason='Saved cookies did not establish an authenticated Dola session; cookies preserved')
                return
            source = Path(r'D:\SKILL VIDEO\Timelapse Phòng thú cưng\10_prompt_timelapse_thi_cong_phong_thu_cung_vip.md')
            prompts = re.findall(r'```(?:markdown)?\s*\n(.*?)```', source.read_text(encoding='utf-8-sig'), re.S)
            if len(prompts) != 10:
                raise RuntimeError(f'Expected 10 source prompts, found {len(prompts)}')
            txt = out / 'prompt_01.txt'
            txt.write_text('PROMPT 01\n' + prompts[0], encoding='utf-8')
            flow = NativeVideoAutomation()
            async def save_video(item):
                response = await context.request.get(item['url'], timeout=180000)
                if not response.ok:
                    raise RuntimeError(f'Video download HTTP {response.status}')
                data = await response.body()
                content_type = response.headers.get('content-type', '')
                if not data or ('video' not in content_type and b'ftyp' not in data[:64]):
                    raise RuntimeError('Returned asset is not a playable video file')
                target = out / 'prompt_01.mp4'
                target.write_bytes(data)
                from video_downloader import VideoDownloader
                metadata = await asyncio.to_thread(VideoDownloader().get_video_info, str(target))
                report('video_downloaded', path=str(target), bytes=len(data), duration=metadata.get('duration'))
            result = await flow.execute_skill_batch(
                page, [prompts[0]], aspect_ratio='9:16', model_version=model,
                account_name=account, prompt_file=str(txt), prompt_numbers=[1],
                duration_target=duration,
                action_delay=6, auto_confirm=True,
                on_video_found=save_video,
                progress_callback=lambda message: report('progress', message=message))
            # Store signed asset URLs locally, rather than exposing them in logs.
            (out / 'video_assets.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            report('video_returned', count=len(result), page_url=page.url)
        except Exception as exc:
            # Network errors can include proxy credentials; report only a
            # classification, retaining page evidence without secret values.
            message = str(exc)
            (out / 'error_trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
            if '710022002' in message:
                reason = 'Dola 710022002: too many requests'
            elif 'AUTH_EXPIRED' in message or 'SKILL_AUTH_REQUIRED' in message:
                reason = 'Dola requires login again after the request'
            elif 'task_id' in message and 'empty' in message:
                reason = 'Dola generation returned task_id is empty'
            elif 'ERR_' in message:
                reason = re.search(r'ERR_[A-Z_]+', message).group(0)
            else:
                reason = type(exc).__name__
            report('stopped', reason=reason)
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            try:
                await page.screenshot(path=str(out / 'last_state.png'))
                (out / 'last_page.txt').write_text(await page.locator('body').inner_text(), encoding='utf-8')
            except Exception:
                pass
            await context.close()
            report('session_closed', cookies_preserved=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--account', default='tunggemini')
    parser.add_argument('--duration', type=int, choices=(15, 30), default=30)
    parser.add_argument('--model', choices=('2.0', '2.5'), default='2.5')
    args = parser.parse_args()
    asyncio.run(main(args.account, args.duration, args.model))
