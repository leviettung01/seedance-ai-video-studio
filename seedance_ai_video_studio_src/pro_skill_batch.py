"""Pro Skill batch runner with account/prompt tracking and extension downloads."""
import asyncio
import json
import re
import time
import uuid
from pathlib import Path

from native_video_automation import NativeVideoAutomation


def assign_prompts(accounts, prompts, per_account=2):
    """Assign consecutive pairs to accounts, retaining original prompt numbers."""
    names = list(dict.fromkeys(a for a in (accounts if isinstance(accounts, (list, tuple)) else [accounts]) if a))
    if not names:
        raise ValueError('Chưa có account để phân bổ prompt.')
    groups = {}
    for start in range(0, len(prompts), per_account):
        account = names[(start // per_account) % len(names)]
        groups.setdefault(account, []).extend(
            (i + 1, prompts[i]) for i in range(start, min(start + per_account, len(prompts)))
        )
    return groups


def _safe_name(value, limit=45):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', str(value)).strip('_')[:limit] or 'account'


class ProSkillBatch:
    def __init__(self):
        self.cancelled = False
        self.current = None
        self.last_failed_prompt = 0
        self.completed_prompt_numbers = []

    def cancel(self):
        self.cancelled = True
        if self.current:
            self.current.cancel()

    async def run(self, account, prompts, brief, count, ratio, image_path,
                  duration=30, show_browser=True, progress=lambda message: None,
                  on_video=lambda info: None, output_dir=None, manifest_path=None):
        from browser_manager import BrowserManager
        from video_downloader import VideoDownloader
        from config import OUTPUT_DIR, UPLOADS_DIR, DATA_DIR, DOLA_URL
        from account_manager import AccountManager
        from proxy_manager import ProxyManager, proxy_endpoint

        if duration not in (15, 30) or count < 1:
            raise ValueError('Thời lượng Pro phải là 15/30s, số lượng phải dương.')
        if prompts and len(prompts) != count:
            raise ValueError('Số lượng video phải bằng số prompt; không lặp prompt ngoài ý muốn.')
        if not prompts:
            prompts = [f'{brief}\nTạo video số {i + 1}/{count} với ý tưởng riêng, dùng cùng Skill đã cài.' for i in range(count)]

        output_dir = Path(output_dir or OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        batch_id = f'pro_{time.strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6]}'
        source_list = Path(UPLOADS_DIR) / f'{batch_id}_all_prompts.txt'
        source_list.parent.mkdir(parents=True, exist_ok=True)
        source_list.write_text(
            '\n\n'.join(f'PROMPT {i:02d}\n{prompt.strip()}' for i, prompt in enumerate(prompts, 1)),
            encoding='utf-8'
        )
        groups = assign_prompts(account, prompts, per_account=2)
        accounts, proxies, downloader = AccountManager(), ProxyManager(), VideoDownloader()
        results = []
        self.last_failed_prompt = 0
        self.completed_prompt_numbers = []
        job_id = f'{batch_id}_job'
        manifest = Path(manifest_path) if manifest_path else Path(DATA_DIR) / 'batch_video_manifest.jsonl'
        manifest.parent.mkdir(parents=True, exist_ok=True)

        def record(row):
            with manifest.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')

        for group_index, (account_name, assigned) in enumerate(groups.items()):
            if self.cancelled:
                raise asyncio.CancelledError()
            worker_id = 40 + group_index
            bm = BrowserManager()
            numbers = [number for number, _ in assigned]
            assigned_prompts = [prompt for _, prompt in assigned]
            native = None
            proxy = proxies.select_profile_proxy(account_name, accounts.get_proxy_for_account(account_name) or '')
            if proxies.pool.enabled and not proxy:
                raise RuntimeError('VPN2Proxy đang bật nhưng chưa có proxy Pháp hợp lệ; không mở mạng trực tiếp.')
            if proxy:
                health = await proxies.test_proxy(proxy)
                if not health.get('success'):
                    raise RuntimeError('Proxy VPN2Proxy không phản hồi; dừng để tránh lộ IP mạng hệ thống.')
            progress(f'Account {account_name}: PROMPT {numbers[0]:02d}–{numbers[-1]:02d}; proxy ' + (proxy_endpoint(proxy) if proxy else 'trực tiếp'))
            try:
                # Pro Chrome must carry the Dola extension too: it assigns
                # prompt/account context and downloads each new no-logo asset.
                await bm.launch_temp_chrome(worker_id, show_browser=show_browser,
                                            load_extension=True, proxy_url=proxy)
                if not await bm.connect_worker(worker_id, setup_extension=True):
                    raise RuntimeError('Không kết nối được Chrome Pro.')
                if not await bm.inject_session_to_worker(worker_id, account_name):
                    raise RuntimeError(f'Không khôi phục được phiên Dola của {account_name}; chưa gửi prompt.')
                page = await bm.get_worker_page(worker_id)
                await page.goto(DOLA_URL, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)
                native = NativeVideoAutomation()
                self.current = native

                async def on_video_found(item):
                    number = int(item['prompt_number'])
                    safe_account = _safe_name(account_name, 40)
                    started = time.time() - 5
                    # Only count files saved by the Dola extension.
                    prefix = f'prompt_{number:02d}_{safe_account}_'
                    ext_file = None
                    deadline = time.monotonic() + 180
                    while time.monotonic() < deadline and not self.cancelled:
                        candidates = [p for p in output_dir.glob(prefix + '*.mp4')
                                      if p.stat().st_mtime >= started and p.stat().st_size > 0]
                        if candidates:
                            ext_file = max(candidates, key=lambda p: p.stat().st_mtime)
                            break
                        await asyncio.sleep(1)
                    if ext_file:
                        path = str(ext_file)
                    else:
                        raise RuntimeError(f'EXTENSION_DOWNLOAD_PENDING: PROMPT {number:02d}; chưa có file extension, không ghi nhận hoàn tất.')
                    if not path or not Path(path).is_file():
                        raise RuntimeError(f'PROMPT {number:02d}: không tải được video.')
                    info = await asyncio.to_thread(downloader.get_video_info, path)
                    actual = float(info.get('duration') or 0)
                    if not info.get('width') or abs(actual - duration) > .25:
                        record({'batch_id': batch_id, 'prompt_number': number, 'job_id': job_id,
                                'account_name': account_name, 'status': 'duration_mismatch',
                                'output_path': path, 'duration': actual, 'video_url': item['url'],
                                'completed_at': time.time()})
                        raise RuntimeError(f'DURATION_MISMATCH: PROMPT {number:02d} yêu cầu {duration}s, file thực tế {actual:.3f}s; đã giữ file.')
                    entry = {'index': number, 'prompt_number': number, 'account_name': account_name,
                             'url': item['url'], 'path': path, 'duration': actual, 'batch_id': batch_id}
                    results.append(entry)
                    self.completed_prompt_numbers.append(number)
                    record({'batch_id': batch_id, 'prompt_number': number, 'job_id': job_id,
                            'account_name': account_name, 'status': 'video_downloaded',
                            'output_path': path, 'duration': actual, 'video_url': item['url'],
                            'completed_at': time.time()})
                    on_video(entry)

                if duration == 30:
                    assigned_file = Path(UPLOADS_DIR) / f'{batch_id}_{_safe_name(account_name, 40)}_{numbers[0]:02d}_{numbers[-1]:02d}.txt'
                    assigned_file.write_text(
                        '\n\n'.join(f'PROMPT {n:02d}\n{p.strip()}' for n, p in assigned),
                        encoding='utf-8')
                    await native.execute_skill_batch(
                        page, assigned_prompts, aspect_ratio=ratio, model_version='2.5',
                        account_name=account_name, progress_callback=progress,
                        prompt_file=str(assigned_file), prompt_numbers=numbers,
                        batch_id=batch_id, job_id=job_id, image_path=image_path,
                        auto_confirm=True, on_video_found=on_video_found)
                else:
                    for number, prompt in assigned:
                        if self.cancelled:
                            raise asyncio.CancelledError()
                        url = await native.execute_generation_flow(
                            page, prompt, aspect_ratio=ratio, image_path=image_path,
                            duration_target=duration, model_version='2.5', account_name=account_name,
                            progress_callback=progress, batch_id=batch_id, prompt_number=number)
                        await on_video_found({'prompt_number': number, 'url': url, 'account_name': account_name})
            except Exception as exc:
                self.last_failed_prompt = (getattr(native, 'last_prompt_number', 0) if native else 0)
                account_state = accounts.get_account(account_name)
                if account_state:
                    if '710022002' in str(exc):
                        account_state.login_status = 'rate_limited'
                    elif 'AUTH_EXPIRED' in str(exc) or 'SKILL_AUTH_REQUIRED' in str(exc):
                        account_state.login_status = 'login_required'
                        account_state.session_health = 0.0
                    accounts.save()
                failed_number = (getattr(native, 'last_prompt_number', 0)
                                 or (numbers[min(len(results), len(numbers) - 1)] if numbers else 0))
                record({'batch_id': batch_id, 'prompt_number': failed_number,
                        'job_id': job_id, 'account_name': account_name,
                        'status': 'failed', 'error': str(exc), 'completed_at': time.time()})
                # Honor Dola's explicit no-retry/refusal response; do not submit
                # the same request through another account or another chat.
                raise
            finally:
                self.current = None
                await bm.cleanup_all()
        return results
