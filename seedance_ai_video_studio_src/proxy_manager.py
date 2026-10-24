# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Universal Proxy Manager & VPN Bridge
Hỗ trợ tất cả các dạng proxy từ Tool Proxy VPN (OCProxy / HMA / WireGuard / PIA / IPv6),
tích hợp Transparent Auth Bridge cho Chrome, và API 5Stars / TM Proxy.
"""

import os
import re
import json
import time
import base64
import httpx
import asyncio
import threading
import socket
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from config import PROXY_POOL_FILE, PROXY_5STARS_API, PROXY_RESOLVE_WAIT
from utils import safe_json_load, safe_json_save, log


def proxy_endpoint(url):
    """Display a proxy endpoint without embedding its credentials."""
    from urllib.parse import urlsplit
    try:
        value = urlsplit(url)
        return f'{value.scheme}://{value.hostname}:{value.port}'
    except ValueError:
        return '(proxy không hợp lệ)'


# ─── OCProxy / HMA Hub DB Discovery ──────────────────────────────────────────

OCPROXY_CANDIDATE_PATHS = [
    r"d:\Proxy\hma_proxy_hub\proxies_db.json",
    r"D:\Proxy\hma_proxy_hub\proxies_db.json",
    r"C:\Proxy\hma_proxy_hub\proxies_db.json",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Proxy", "hma_proxy_hub", "proxies_db.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hma_proxy_hub", "proxies_db.json"),
]


def find_ocproxy_db_path() -> Optional[str]:
    """Tìm đường dẫn tệp proxies_db.json của Tool Proxy VPN."""
    for p in OCPROXY_CANDIDATE_PATHS:
        if os.path.isfile(p):
            return p
    return None


def import_from_ocproxy_hub() -> List[Dict[str, Any]]:
    """Đọc toàn bộ danh sách proxy đang chạy từ Tool Proxy VPN."""
    farm = import_from_proxy_farm()
    path = find_ocproxy_db_path()
    if not path:
        return farm
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            running = list(farm)
            for proxy in data:
                if proxy.get('status') != 'running':
                    continue
                try:
                    with socket.create_connection(('127.0.0.1', int(proxy['port'])), timeout=.3):
                        if not any(p.get('port') == proxy.get('port') for p in running):
                            running.append(proxy)
                except (OSError, ValueError, KeyError):
                    continue
            return running
    except Exception as e:
        log("Proxy Hub", f"Lỗi đọc {path}: {e}")
    return farm


def import_from_proxy_farm() -> List[Dict[str, Any]]:
    """Discover healthy independent tunnels; never import a merely open proxy port."""
    try:
        with httpx.Client(trust_env=False, timeout=2.0) as client:
            response = client.get('http://127.0.0.1:8090/api/status')
            response.raise_for_status()
            data = response.json()
        auth = data.get('auth') or {}
        result = []
        for row in data.get('rows', []):
            if row.get('state') != 'running' or row.get('ok') is not True or not row.get('ip'):
                continue
            port = int(row['port'])
            if not 1 <= port <= 65535:
                continue
            with socket.create_connection(('127.0.0.1', port), timeout=.3):
                row_auth = row.get('auth') or auth
                result.append({
                    'port': port, 'status': 'running',
                    'auth_user': row_auth.get('user', ''), 'auth_pass': row_auth.get('pass', ''),
                    'country_name': row.get('name') or row.get('country', ''),
                    'country_code': row.get('country', ''),
                    'real_wan_ip': row['ip'], 'provider': row.get('provider'),
                    'source': 'proxy-farm', 'farm_key': row.get('key'),
                })
        return result
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError):
        return []


def find_ocproxy_credentials_for_port(port: int) -> Tuple[str, str]:
    """Tự động tra cứu user/pass cho port từ database của Tool Proxy VPN nếu có."""
    proxies = import_from_ocproxy_hub()
    for p in proxies:
        if p.get("port") == port:
            return p.get("auth_user", ""), p.get("auth_pass", "")
    return "", ""


# ─── Universal Proxy Spec Parser ─────────────────────────────────────────────

def parse_proxy_spec(raw: str) -> Optional[Dict[str, Any]]:
    """Phân tích bất kỳ định dạng proxy nào thành cấu trúc chuẩn:
    - 127.0.0.1:10000
    - 127.0.0.1:10000:user:pass
    - user:pass@127.0.0.1:10000
    - user:pass:127.0.0.1:10000
    - http://user:pass@127.0.0.1:10000
    - socks5://user:pass@127.0.0.1:20000
    - socks5://127.0.0.1:20000
    - http://127.0.0.1:10000
    """
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return None

    scheme = "http"
    u, p, host, port_str = "", "", "", ""

    # 1. Có URL scheme (http://, socks5://...)
    if raw.startswith(("http://", "https://", "socks5://", "socks4://")):
        scheme_part, rest = raw.split("://", 1)
        scheme = scheme_part.lower()
        if "@" in rest:
            userpass, hostport = rest.split("@", 1)
            u, p = userpass.split(":", 1) if ":" in userpass else (userpass, "")
            host, port_str = hostport.split(":", 1) if ":" in hostport else (hostport, "80")
        else:
            host, port_str = rest.split(":", 1) if ":" in rest else (rest, "80")

    # 2. Định dạng IP:PORT:USER:PASS
    elif raw.count(":") == 3:
        parts = raw.split(":")
        host, port_str, u, p = parts[0], parts[1], parts[2], parts[3]

    # 3. Định dạng USER:PASS@IP:PORT
    elif "@" in raw:
        userpass, hostport = raw.split("@", 1)
        u, p = userpass.split(":", 1) if ":" in userpass else (userpass, "")
        host, port_str = hostport.split(":", 1) if ":" in hostport else (hostport, "80")

    # 4. Định dạng IP:PORT
    elif raw.count(":") == 1:
        parts = raw.split(":")
        if parts[1].isdigit():
            host, port_str = parts[0], parts[1]
        else:
            return None  # Không phải IP:PORT
    else:
        return None

    # Validate port
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            return None
    except ValueError:
        return None

    # Nếu chưa có user/pass, thử tra cứu tự động từ Tool Proxy VPN (nếu là local port)
    if not u and not p and host in ("127.0.0.1", "localhost", "0.0.0.0") or host.startswith("192.168."):
        db_user, db_pass = find_ocproxy_credentials_for_port(port)
        if db_user:
            u, p = db_user, db_pass

    # Build canonical URLs
    if u and p:
        canonical_url = f"{scheme}://{u}:{p}@{host}:{port}"
    else:
        canonical_url = f"{scheme}://{host}:{port}"

    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "user": u,
        "pass": p,
        "url": canonical_url,
        "clean_url": f"{scheme}://{host}:{port}"
    }


def normalize_proxy_to_url(raw: str) -> Optional[str]:
    """Chuyển đổi chuỗi proxy bất kỳ thành URL chuẩn để kết nối."""
    spec = parse_proxy_spec(raw)
    return spec["url"] if spec else None


# ─── Transparent Local Proxy Auth Bridge ─────────────────────────────────────

class ProxyAuthBridge:
    """Cầu nối chuyển tiếp cục bộ (Local Transparent Auth Bridge).
    Tự động gắn header `Proxy-Authorization: Basic ...` để trình duyệt Chrome
    kết nối thẳng mượt mà mà không bao giờ bị popup xác thực hoặc lỗi ERR_INVALID_AUTH_CREDENTIALS.
    """
    def __init__(self, target_host: str, target_port: int, user: str = "", pass_: str = "", listen_port: int = 0):
        self.target_host = target_host
        self.target_port = int(target_port)
        self.user = user
        self.pass_ = pass_
        self.auth_header = "Basic " + base64.b64encode(f"{user}:{pass_}".encode()).decode() if user and pass_ else None
        self.listen_port = listen_port
        self.server = None

    async def start(self) -> int:
        """Khởi động bridge trên 127.0.0.1 với port tự cấp phát."""
        self.server = await asyncio.start_server(self._handle_client, "127.0.0.1", self.listen_port)
        self.listen_port = self.server.sockets[0].getsockname()[1]
        return self.listen_port

    async def stop(self):
        """Dừng bridge và đóng toàn bộ socket."""
        if self.server:
            try:
                self.server.close()
                await self.server.wait_closed()
            except Exception:
                pass
            self.server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            req_line = await reader.readline()
            if not req_line:
                writer.close()
                return

            headers = []
            while True:
                line = await reader.readline()
                if line == b"\r\n" or not line:
                    break
                # Bỏ qua header auth từ client nếu có
                if not line.lower().startswith(b"proxy-authorization:"):
                    headers.append(line)

            parts = req_line.decode("latin1", errors="replace").split()
            if not parts:
                writer.close()
                return

            method = parts[0].upper()
            target = parts[1] if len(parts) > 1 else ""
            proto = parts[2] if len(parts) > 2 else "HTTP/1.1"

            # Mở kết nối tới proxy đích (Tool VPN)
            u_reader, u_writer = await asyncio.open_connection(self.target_host, self.target_port)

            if method == "CONNECT":
                # HTTPS CONNECT Tunnel
                req = f"CONNECT {target} {proto}\r\nHost: {target}\r\n"
                if self.auth_header:
                    req += f"Proxy-Authorization: {self.auth_header}\r\n"
                req += "Proxy-Connection: Keep-Alive\r\n\r\n"
                u_writer.write(req.encode("latin1"))
                await u_writer.drain()

                # Đọc phản hồi từ proxy đích
                u_res = await u_reader.readline()
                while True:
                    l = await u_reader.readline()
                    if l == b"\r\n" or not l:
                        break

                if b"200" in u_res:
                    writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                    await writer.drain()
                    await self._pipe(reader, writer, u_reader, u_writer)
                else:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    u_writer.close()
            else:
                # Direct HTTP request (GET, POST...)
                req = f"{method} {target} {proto}\r\n"
                if self.auth_header:
                    req += f"Proxy-Authorization: {self.auth_header}\r\n"
                for h in headers:
                    req += h.decode("latin1", errors="replace")
                req += "\r\n"
                u_writer.write(req.encode("latin1"))
                await u_writer.drain()
                await self._pipe(reader, writer, u_reader, u_writer)

        except Exception:
            try:
                writer.close()
            except Exception:
                pass

    async def _pipe(self, r1, w1, r2, w2):
        async def forward(r, w):
            try:
                while True:
                    data = await r.read(65536)
                    if not data:
                        break
                    w.write(data)
                    await w.drain()
            except Exception:
                pass
            finally:
                try:
                    w.close()
                except Exception:
                    pass

        await asyncio.gather(forward(r1, w2), forward(r2, w1))


class ProxyAuthBridgeManager:
    """Quản lý vòng đời các Auth Bridge cho Chrome instances.
    Chạy trên một background thread riêng biệt để các socket server không bao giờ bị ngắt
    ngay cả khi worker hoặc thread UI chuyển trạng thái.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._bridges = {}
            cls._instance._loop = None
            cls._instance._thread = None
            cls._instance._lock = threading.Lock()
            cls._instance._ensure_loop()
        return cls._instance

    def _ensure_loop(self):
        with self._lock:
            if self._loop is None or not self._loop.is_running():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever,
                    daemon=True,
                    name="ProxyAuthBridgeDaemon"
                )
                self._thread.start()

    async def _prepare_internal(self, proxy_str: str, session_key: str = "") -> Tuple[str, Optional[ProxyAuthBridge]]:
        if not proxy_str:
            return "", None

        spec = parse_proxy_spec(proxy_str)
        if not spec:
            return proxy_str, None

        if spec.get("user") and spec.get("pass"):
            # Cần Auth Bridge
            if session_key and session_key in self._bridges:
                old_bridge = self._bridges.pop(session_key, None)
                if old_bridge:
                    await old_bridge.stop()

            bridge = ProxyAuthBridge(spec["host"], spec["port"], spec["user"], spec["pass"])
            bridge_port = await bridge.start()
            if session_key:
                self._bridges[session_key] = bridge

            log("Proxy Bridge", f"⚡ Kích hoạt Auth Bridge [127.0.0.1:{bridge_port}] -> {spec['host']}:{spec['port']} ({spec['user']})")
            return f"http://127.0.0.1:{bridge_port}", bridge
        else:
            return spec["clean_url"], None

    async def _stop_internal(self, session_key: str):
        bridge = self._bridges.pop(session_key, None)
        if bridge:
            await bridge.stop()

    async def _stop_all_internal(self):
        for k in list(self._bridges.keys()):
            await self._stop_internal(k)

    async def prepare_chrome_proxy(self, proxy_str: str, session_key: str = "") -> Tuple[str, Optional[ProxyAuthBridge]]:
        """Chuẩn bị tham số proxy `--proxy-server=` cho Chrome (bất đồng bộ)."""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._prepare_internal(proxy_str, session_key), self._loop)
        return await asyncio.wrap_future(fut)

    def prepare_chrome_proxy_sync(self, proxy_str: str, session_key: str = "") -> Tuple[str, Optional[ProxyAuthBridge]]:
        """Chuẩn bị tham số proxy `--proxy-server=` cho Chrome (đồng bộ - dùng cho GUI thread)."""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._prepare_internal(proxy_str, session_key), self._loop)
        return fut.result(timeout=10)

    async def stop_bridge(self, session_key: str):
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._stop_internal(session_key), self._loop)
        await asyncio.wrap_future(fut)

    def stop_bridge_sync(self, session_key: str):
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._stop_internal(session_key), self._loop)
        try:
            fut.result(timeout=5)
        except Exception:
            pass

    async def stop_all(self):
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._stop_all_internal(), self._loop)
        await asyncio.wrap_future(fut)

    def stop_all_sync(self):
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(self._stop_all_internal(), self._loop)
        try:
            fut.result(timeout=5)
        except Exception:
            pass


_global_bridge_manager = ProxyAuthBridgeManager()

def get_bridge_manager() -> ProxyAuthBridgeManager:
    return _global_bridge_manager


# ─── ProxyPool & ProxyManager ────────────────────────────────────────────────

@dataclass
class ProxyPool:
    """Cấu trúc dữ liệu proxy pool — khớp proxy_pool.json."""
    enabled: bool = True                            # Bật/Tắt chế độ Proxy toàn hệ thống
    source: str = "vpn_tool"                        # "vpn_tool" (Tool VPN2proxy) | "custom" (Proxy ngoài riêng)
    vpn_auto_rotate: bool = True                    # Hub rotates exit IP every 300 seconds
    proxies: list = field(default_factory=list)     # Danh sách proxy từ Tool VPN
    custom_proxies: list = field(default_factory=list) # Danh sách proxy ngoài riêng của người dùng
    carrier: str = "random"                         # "random" | "viettel" | "vinaphone" | "mobifone"
    province: str = "0"                             # Mã tỉnh thành (0 = random)


class ProxyManager:
    """Quản lý pool proxy xoay vòng, tích hợp Tool Proxy VPN và API 5Stars."""

    def __init__(self):
        self.pool = ProxyPool()
        self._current_slot = 0    # Slot index xoay vòng
        self._resolved_cache: dict[str, str] = {}  # key → http://IP:PORT
        self.bridge_mgr = get_bridge_manager()
        self.load()
        from vpn_rotation_client import start_heartbeat
        start_heartbeat()

    @property
    def is_enabled(self) -> bool:
        """Kiểm tra chế độ proxy có đang BẬT không."""
        return bool(self.pool.enabled)

    # ─── Load / Save ──────────────────────────────────────────────────────

    def load(self):
        """Đọc proxy pool từ file."""
        data = safe_json_load(PROXY_POOL_FILE, {})
        self.pool.enabled = bool(data.get("enabled", True))
        self.pool.source = str(data.get("source", "vpn_tool"))
        self.pool.vpn_auto_rotate = bool(data.get('vpn_auto_rotate', True))
        self.pool.proxies = data.get("proxies", [])
        self.pool.custom_proxies = data.get("custom_proxies", [])
        self.pool.carrier = data.get("5stars_carrier", "random")
        self.pool.province = data.get("5stars_province", "0")
        if self.pool.proxies or self.pool.custom_proxies:
            status_str = "BẬT" if self.pool.enabled else "TẮT"
            source_str = "Tool VPN2proxy" if self.pool.source == "vpn_tool" else "Proxy ngoài"
            log("Proxy Pool", f"Loaded Proxy Pool: [{status_str}] - Nguồn: {source_str} ({len(self.pool.proxies)} VPN, {len(self.pool.custom_proxies)} Custom)")

    def save(self):
        """Ghi proxy pool ra file."""
        data = {
            "enabled": self.pool.enabled,
            "source": self.pool.source,
            "vpn_auto_rotate": self.pool.vpn_auto_rotate,
            "proxies": self.pool.proxies,
            "custom_proxies": self.pool.custom_proxies,
            "5stars_carrier": self.pool.carrier,
            "5stars_province": self.pool.province,
        }
        safe_json_save(PROXY_POOL_FILE, data)
        from vpn_rotation_client import notify_config_changed
        notify_config_changed()

    def update_pool(self, proxies: list, carrier: str = "random", province: str = "0", enabled: bool = True, source: str = "vpn_tool", custom_proxies: list = None, vpn_auto_rotate: Optional[bool] = None):
        """Cập nhật toàn bộ proxy pool."""
        self.pool.enabled = bool(enabled)
        self.pool.source = str(source)
        if vpn_auto_rotate is not None:
            self.pool.vpn_auto_rotate = bool(vpn_auto_rotate)
        if source == "vpn_tool" or proxies:
            self.pool.proxies = proxies
        if custom_proxies is not None:
            self.pool.custom_proxies = custom_proxies
        self.pool.carrier = carrier
        self.pool.province = province
        self.save()
        log("Proxy Pool", f"Đã lưu: Proxy={'BẬT' if enabled else 'TẮT'} | Nguồn={source} | {len(self.pool.proxies)} VPN | {len(self.pool.custom_proxies)} Custom")

    def get_pool_info(self) -> dict:
        """Trả về thông tin proxy pool."""
        return {
            "enabled": self.pool.enabled,
            "source": self.pool.source,
            "vpn_auto_rotate": self.pool.vpn_auto_rotate,
            "vpn_rotate_interval_seconds": 300,
            "proxies": self.pool.proxies,
            "custom_proxies": self.pool.custom_proxies,
            "5stars_carrier": self.pool.carrier,
            "5stars_province": self.pool.province,
        }

    def get_active_proxy_list(self) -> list:
        """Lấy danh sách proxy đang được kích hoạt theo nguồn đã chọn."""
        if not self.pool.enabled:
            return []
        if self.pool.source == "custom":
            return self.pool.custom_proxies or self.pool.proxies
        return self.pool.proxies or self.pool.custom_proxies

    def select_profile_proxy(self, name, saved=''):
        """VPN mode follows the current pool, including refreshed per-port credentials."""
        if not self.pool.enabled: return ''
        active = self.pool.proxies if self.pool.source == 'vpn_tool' else self.get_active_proxy_list()
        if self.pool.source != 'vpn_tool' and saved: return saved
        if saved in active:
            selected = saved
        elif not active:
            return ''
        else:
            import hashlib
            index = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], 'big') % len(active)
            selected = active[index]
        # The VPN pool stores host:port:user:password. Browser launchers need
        # the canonical URL with URL-escaped credentials for the auth bridge.
        spec = parse_proxy_spec(selected)
        if self.pool.source == 'vpn_tool' and spec:
            return spec['url']
        return selected

    def import_from_ocproxy_hub(self) -> int:
        """Tự động đồng bộ toàn bộ proxy đang chạy từ Tool Proxy VPN vào pool."""
        proxies = import_from_ocproxy_hub()
        if not proxies:
            return 0
        new_list = []
        for p in proxies:
            port = p.get("port")
            user = p.get("auth_user", "")
            pass_ = p.get("auth_pass", "")
            if user and pass_:
                new_list.append(f"127.0.0.1:{port}:{user}:{pass_}")
            else:
                new_list.append(f"127.0.0.1:{port}")
        self.update_pool(new_list, carrier=self.pool.carrier, province=self.pool.province, enabled=self.pool.enabled, source="vpn_tool", custom_proxies=self.pool.custom_proxies)
        return len(new_list)

    # ─── Resolve Proxy Key (5Stars / External API) ─────────────────────────

    async def resolve_proxy_key(self, api_key: str) -> Optional[str]:
        """Gọi 5Stars API để lấy proxy IP:PORT từ API key."""
        short_key = api_key[:8] + "..." if len(api_key) > 8 else api_key
        log("Proxy 5Stars", f"Requesting key={short_key}...")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(PROXY_5STARS_API, params={
                    "key": api_key,
                    "nhamang": self.pool.carrier,
                    "tinhthanh": self.pool.province,
                })
                text = resp.text.strip()

                if "LOI" in text or "error" in text.lower():
                    log("Proxy 5Stars", f"Key {short_key} LOI: {text}")
                    return None

                match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", text)
                if match:
                    ip, port = match.group(1), match.group(2)
                    proxy_url = f"http://{ip}:{port}"
                    self._resolved_cache[api_key] = proxy_url
                    log("Proxy Login", f"Resolved key -> {proxy_url} (IP: {ip})")
                    return proxy_url

                parts = text.split(":")
                if len(parts) == 2:
                    proxy_url = f"http://{parts[0]}:{parts[1]}"
                    self._resolved_cache[api_key] = proxy_url
                    return proxy_url

                return None

        except Exception as e:
            log("Proxy 5Stars", f"Lỗi kết nối API: {e}")
            return None

    # ─── Get Proxy for Account ───────────────────────────────────────────

    async def get_proxy_for_account(self, account_name: str, account_proxy: str = "") -> Optional[str]:
        """Lấy proxy cho account. Nếu chế độ proxy bị TẮT toàn hệ thống thì trả về None."""
        if not self.pool.enabled:
            log("Proxy", f"Account '{account_name}' -> Chế độ Proxy đang TẮT (Chạy mạng trực tiếp Direct IP).")
            return None

        # 1. Ưu tiên proxy riêng của account nếu có
        if account_proxy:
            spec = parse_proxy_spec(account_proxy)
            if spec:
                return spec["url"]
            # Không phải IP:Port -> Thử resolve API key
            resolved = await self.resolve_proxy_key(account_proxy)
            if resolved:
                return resolved

        # 2. Lấy danh sách proxy theo nguồn đã chọn (Tool VPN2proxy hoặc Proxy ngoài)
        active_list = self.get_active_proxy_list()
        if not active_list:
            log("Proxy", f"Account '{account_name}' không có proxy. Pool đang trống.")
            return None

        key = active_list[self._current_slot % len(active_list)]
        self._current_slot += 1

        # Kiểm tra nếu là direct proxy (IP:Port / VPN Tool / Custom)
        spec = parse_proxy_spec(key)
        if spec:
            source_tag = "VPN2proxy" if self.pool.source == "vpn_tool" else "Proxy Ngoài"
            log("Proxy", f"Account '{account_name}' -> Proxy ({source_tag}) #{self._current_slot}: {proxy_endpoint(spec['url'])}")
            return spec["url"]

        # Nếu là chuỗi ký tự không có port -> Coi là API key 5Stars
        resolved = await self.resolve_proxy_key(key)
        return resolved

    async def rotate_proxy(self, slot_index: int = 0) -> Optional[str]:
        """Xoay IP mới cho một slot cụ thể."""
        if not self.pool.proxies:
            return None

        idx = slot_index % len(self.pool.proxies)
        key = self.pool.proxies[idx]
        spec = parse_proxy_spec(key)
        if spec:
            return spec["url"]

        proxy_url = await self.resolve_proxy_key(key)
        if proxy_url:
            await asyncio.sleep(PROXY_RESOLVE_WAIT)
        return proxy_url

    # ─── Test Proxy ───────────────────────────────────────────────────────

    async def test_proxy(self, proxy_url: str) -> dict:
        """Kiểm tra proxy bằng cách truy cập ipify / httpbin và đo độ trễ."""
        spec = parse_proxy_spec(proxy_url)
        test_url = spec["url"] if spec else proxy_url

        start = time.time()
        try:
            # Tương thích tất cả các phiên bản httpx (proxy= hoặc proxies=)
            try:
                client = httpx.AsyncClient(proxy=test_url, timeout=12)
            except TypeError:
                client = httpx.AsyncClient(proxies={"http://": test_url, "https://": test_url}, timeout=12)

            async with client:
                resp = await client.get("https://api.ipify.org?format=json")
                latency = int((time.time() - start) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "ip": data.get("ip", "unknown"),
                        "latency_ms": latency,
                        "proxy": proxy_url,
                        "status_code": 200
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status_code}",
                        "proxy": proxy_url,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "proxy": proxy_url,
            }
