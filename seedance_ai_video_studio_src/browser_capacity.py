"""One shared limit for account profiles and video workers in this tool process."""
import threading
import time
import psutil

MAX_BROWSERS = 10
_lock = threading.Lock()
_pending = set()
_started = set()
_observed = set()
_checked_at = 0.0


def reserve_browser(key):
    global _observed, _checked_at
    with _lock:
        if time.monotonic() - _checked_at > 10:
            observed = set()
            for process in psutil.process_iter(['name']):
                try:
                    if (process.info['name'] or '').lower() != 'chrome.exe':
                        continue
                    args = process.cmdline()
                    if any(arg.startswith('--type=') for arg in args):
                        continue
                    if any(arg.startswith('--user-data-dir=') and
                           ('chrome_user_data_dola' in arg or 'seedance_worker_' in arg)
                           for arg in args):
                        observed.add(process.pid)
                except (psutil.Error, OSError):
                    pass
            _observed = observed
            _checked_at = time.monotonic()
        active = {pid for pid in _observed | _started if psutil.pid_exists(pid)}
        if key in _pending or len(active) + len(_pending) >= MAX_BROWSERS:
            raise RuntimeError('Đã đạt tối đa 10 Chrome/luồng của tool. Đóng bớt profile trước khi mở thêm.')
        _pending.add(key)


def browser_started(key, pid):
    with _lock:
        _pending.discard(key)
        _started.add(pid)


def release_reservation(key):
    with _lock:
        _pending.discard(key)
