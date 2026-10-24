"""Start the user's local VPN2Proxy launcher on demand, outside the Qt thread."""
import os
import pathlib
import subprocess
import threading
import time
import httpx

_lock = threading.Lock()
LAUNCHER = pathlib.Path('D:/Proxy/KHOI_DONG_TOOL_PROXY.bat')


def hub_ready():
    try:
        with httpx.Client(trust_env=False, timeout=2) as client:
            reply = client.get('http://127.0.0.1:9090/api/hma/status')
            return reply.status_code == 200 and reply.json().get('engine') == 'docker'
    except (httpx.HTTPError, ValueError):
        return False


def ensure_vpn_hub(wait_seconds=120):
    if hub_ready(): return
    with _lock:
        if hub_ready(): return
        if not LAUNCHER.is_file():
            raise RuntimeError('Không tìm thấy launcher VPN2Proxy trong D:/Proxy.')
        subprocess.Popen([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(LAUNCHER)],
            cwd=str(LAUNCHER.parent), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if hub_ready(): return
            time.sleep(2)
        raise RuntimeError('VPN2Proxy chưa sẵn sàng; kiểm tra Docker Desktop và HMA đăng nhập. Không dùng mạng trực tiếp thay thế.')
