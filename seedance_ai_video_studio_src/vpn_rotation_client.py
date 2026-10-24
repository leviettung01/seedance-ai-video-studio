"""Lease the selected VPN2Proxy ports to the hub's shared 5-minute clock."""
import threading
from urllib.parse import urlsplit

import httpx


def selected_ports(data):
    if not (data.get('enabled', True) and data.get('source', 'vpn_tool') == 'vpn_tool'
            and data.get('vpn_auto_rotate', True)):
        return []
    ports = set()
    for raw in data.get('proxies', []):
        try:
            text = str(raw).strip()
            if '://' not in text and '@' not in text and not text.startswith('['):
                host, port = text.split(':')[:2]
                port = int(port)
            else:
                parsed = urlsplit(text if '://' in text else 'http://' + text)
                host, port = parsed.hostname, parsed.port
            if host in ('127.0.0.1', 'localhost', '::1') and port and 1 <= port <= 65535:
                ports.add(port)
        except (ValueError, TypeError):
            continue
    return sorted(ports)


def sync_rotation(data):
    ports = selected_ports(data)
    try:
        with httpx.Client(trust_env=False, timeout=3) as client:
            response = client.post('http://127.0.0.1:9090/api/rotation/client', json={
                'client_id': 'seedance-studio', 'enabled': bool(ports), 'ports': ports})
            response.raise_for_status()
            return response.json()
    except Exception:
        return {'success': False, 'error': 'VPN2Proxy chưa chạy hoặc cần mở lại để nạp chức năng xoay IP.'}


_started = False
_lock = threading.Lock()
_wake = threading.Event()


def notify_config_changed():
    _wake.set()


def start_heartbeat():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    def run():
        from config import PROXY_POOL_FILE
        from utils import safe_json_load
        while True:
            _wake.clear()
            try:
                sync_rotation(safe_json_load(PROXY_POOL_FILE, {}))
            except Exception:
                pass
            _wake.wait(30)
    threading.Thread(target=run, name='studio-vpn-rotation-lease', daemon=True).start()
