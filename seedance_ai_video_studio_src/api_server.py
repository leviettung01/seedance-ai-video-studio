# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — FastAPI Server
Tất cả REST API endpoints phục vụ GUI + Extension communication.
"""

import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from config import (
    APP_NAME, APP_VERSION, API_PORT,
    OUTPUT_DIR, UPLOADS_DIR, EXTENSION_DIR, BASE_DIR,
)
from utils import (
    setup_logging, log_bootstrap, clean_temp_sessions,
    get_device_id, generate_upload_id, generate_bypass_id,
    log, get_timestamp,
)
from account_manager import AccountManager
from proxy_manager import ProxyManager
from browser_manager import BrowserManager
from dola_automation import DolaAutomation
from video_downloader import VideoDownloader
from job_manager import JobManager


# ─── Khởi tạo App & Managers ─────────────────────────────────────────────────

app = FastAPI(title=APP_NAME, version=APP_VERSION)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Managers (khởi tạo singleton)
account_manager = AccountManager()
proxy_manager = ProxyManager()
browser_manager = BrowserManager()
dola_automation = DolaAutomation()
video_downloader = VideoDownloader()
job_manager = JobManager()
job_manager.inject_dependencies(
    account_manager, proxy_manager,
    browser_manager, dola_automation, video_downloader
)

# Static Files
assets_dir = os.path.join(BASE_DIR, "assets")
os.makedirs(assets_dir, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ─── Startup Event ───────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    setup_logging()
    log_bootstrap()
    clean_temp_sessions()


# ─── Pydantic Models ─────────────────────────────────────────────────────────

class AddAccountRequest(BaseModel):
    name: str
    login_type: str = "google"
    gmail_email: str = ""
    gmail_password: str = ""
    proxy: str = ""
    quota_max: int = 4
    fb_uid: str = ""
    fb_password: str = ""
    fb_2fa: str = ""
    fb_cookies: str = ""
    fb_token: str = ""

class ProxyPoolRequest(BaseModel):
    enabled: bool = True
    source: str = "vpn_tool"
    vpn_auto_rotate: Optional[bool] = None
    proxies: list[str] = []
    custom_proxies: list[str] = []
    carrier: str = "random"
    province: str = "0"

class AccountProxyRequest(BaseModel):
    account_name: str
    proxy: str

class CreateVideoRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    mode: str = "standard"
    duration_target: int = 31
    model_version: str = "2.5"
    enable_upscale: bool = True
    upscale_target: str = "2K"
    image_path: str = ""

class LicenseRequest(BaseModel):
    license_key: str

class OpenProfileRequest(BaseModel):
    account_name: str
    proxy_url: str = ""

class SaveDolaSessionRequest(BaseModel):
    account_name: str
    cookies: list[dict] = []
    local_storage: Optional[dict] = None
    cookie_string: Optional[str] = ""
    fb_uid: Optional[str] = ""


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

# ─── GUI ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_gui():
    """Phục vụ trang GUI chính."""
    index_path = os.path.join(assets_dir, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Seedance AI Video Studio</h1><p>GUI not found. Place index.html in assets/</p>")


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


# ─── Accounts ────────────────────────────────────────────────────────────────

@app.get("/api/accounts")
async def get_accounts():
    """Danh sách tất cả accounts + trạng thái."""
    return {"accounts": account_manager.get_all()}

@app.post("/api/accounts/add")
async def add_account(req: AddAccountRequest):
    """Thêm account mới."""
    try:
        kwargs = req.dict()
        name = kwargs.pop("name")
        login_type = kwargs.pop("login_type")
        acc = account_manager.add_account(name, login_type, **kwargs)
        return {"success": True, "account": acc.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/accounts/{name}")
async def delete_account(name: str):
    """Xóa account."""
    ok = account_manager.delete_account(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Account '{name}' not found")
@app.post("/api/accounts/save-dola-session")
async def save_dola_session(req: SaveDolaSessionRequest):
    """Lưu session cookies & localStorage trích xuất từ Extension vào SessionStore & AccountManager."""
    import time
    from session_store import SessionStore, parse_bulk_dola_cookies
    ss = SessionStore()
    name = req.account_name.strip()
    if not name:
        name = f"dola_{int(time.time())}"

    cookies = req.cookies or []
    if not cookies and req.cookie_string:
        parsed = parse_bulk_dola_cookies(req.cookie_string, default_name=name)
        if parsed:
            cookies = parsed[0][1]

    if not cookies:
        raise HTTPException(status_code=400, detail="Không có cookies nào được gửi lên.")

    # 1. Lưu vào SessionStore (accounts_sessions.json)
    ss.save_session(name, cookies, req.local_storage or {})

    # 2. Tạo hoặc cập nhật account trong AccountManager (accounts_state.json)
    acc = account_manager.get_account(name)
    if not acc:
        login_type = "facebook" if req.fb_uid else "cookies"
        acc = account_manager.add_account(
            name=name,
            login_type=login_type,
            fb_uid=req.fb_uid or "",
            fb_cookies=req.cookie_string or ""
        )
    acc.dola_session_saved = True
    acc.cookie_count = len(cookies)
    if req.fb_uid and not acc.fb_uid:
        acc.fb_uid = req.fb_uid
    if req.cookie_string:
        acc.fb_cookies = req.cookie_string
    account_manager.save()

    log("API", f"✅ Đã lưu session Dola cho '{name}' ({len(cookies)} cookies) từ Extension.")
    return {
        "success": True,
        "account_name": name,
        "cookies_count": len(cookies),
        "message": f"Đã lưu session cho '{name}' thành công!"
    }


@app.get("/api/accounts/export-cookies")
async def export_cookies():
    """Xuất toàn bộ cookies & session của tất cả tài khoản phục vụ Extension hoặc backup."""
    from session_store import SessionStore
    ss = SessionStore()
    ss.load()
    account_manager.load()

    results = []
    multi_dict = {}

    for acc_name, sdata in ss._sessions.items():
        raw_cookies = sdata.get("cookies", [])
        clean_cookies = []
        cookie_kv_pairs = []
        for c in raw_cookies:
            c_dict = {
                "name": str(c.get("name", "")).strip(),
                "value": str(c.get("value", "")).strip(),
                "domain": str(c.get("domain", ".dola.com")),
                "path": str(c.get("path", "/")),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
                "sameSite": str(c.get("sameSite", "Lax"))
            }
            if "expirationDate" in c:
                c_dict["expirationDate"] = c["expirationDate"]
            elif "expires" in c:
                c_dict["expirationDate"] = c["expires"]
            clean_cookies.append(c_dict)
            cookie_kv_pairs.append(f"{c_dict['name']}={c_dict['value']}")

        ls = sdata.get("local_storage", {})
        acc = account_manager.get_account(acc_name)
        fb_uid = (acc.fb_uid if acc else "") or sdata.get("fb_uid", "")
        dola_uid = (acc.dola_uid if acc else "") or sdata.get("dola_uid", "")

        item = {
            "name": acc_name,
            "cookies": clean_cookies,
            "local_storage": ls,
            "cookie_string": "; ".join(cookie_kv_pairs),
            "fb_uid": fb_uid,
            "dola_uid": dola_uid,
            "cookies_count": len(clean_cookies),
            "saved_at": sdata.get("saved_at", 0),
            "quota_used": acc.quota_used if acc else 0,
            "quota_max": acc.quota_max if acc else 4,
            "status": acc.status if acc else "active"
        }
        results.append(item)
        multi_dict[acc_name] = clean_cookies

    return {
        "success": True,
        "total": len(results),
        "accounts": results,
        "dola_all_cookies": multi_dict
    }


@app.post("/api/accounts/export-files")
async def export_files_on_disk():
    """Ghi tự động các tệp cookies (DOLA_ALL_ACCOUNTS_COOKIES.json, DOLA_ACCOUNTS_ARRAY.json, DOLA_COOKIE_STRINGS.txt) ra ổ đĩa F:/Seedance."""
    from session_store import SessionStore
    ss = SessionStore()
    ss.load()
    account_manager.load()

    multi_accounts = {}
    array_accounts = []
    via_lines = []

    target_dir = "F:/Seedance"
    indiv_dir = os.path.join(target_dir, "Dola_Account_Cookies_Individual")
    os.makedirs(indiv_dir, exist_ok=True)

    for acc_name, sdata in ss._sessions.items():
        raw_cookies = sdata.get("cookies", [])
        clean_cookies = []
        cookie_kv_pairs = []
        for c in raw_cookies:
            c_dict = {
                "name": str(c.get("name", "")).strip(),
                "value": str(c.get("value", "")).strip(),
                "domain": str(c.get("domain", ".dola.com")),
                "path": str(c.get("path", "/")),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
                "sameSite": str(c.get("sameSite", "Lax"))
            }
            if "expirationDate" in c:
                c_dict["expirationDate"] = c["expirationDate"]
            elif "expires" in c:
                c_dict["expirationDate"] = c["expires"]
            clean_cookies.append(c_dict)
            cookie_kv_pairs.append(f"{c_dict['name']}={c_dict['value']}")

        acc = account_manager.get_account(acc_name)
        fb_uid = (acc.fb_uid if acc else "") or sdata.get("fb_uid", "")
        dola_uid = (acc.dola_uid if acc else "") or sdata.get("dola_uid", "")

        multi_accounts[acc_name] = clean_cookies
        array_accounts.append({
            "name": acc_name,
            "cookies": clean_cookies,
            "local_storage": sdata.get("local_storage", {}),
            "fb_uid": fb_uid,
            "dola_uid": dola_uid
        })

        # Lưu file từng account
        safe_fname = acc_name.replace(" ", "_").replace("/", "_").replace("\\", "_") + ".json"
        with open(os.path.join(indiv_dir, safe_fname), "w", encoding="utf-8") as f:
            json.dump(clean_cookies, f, ensure_ascii=False, indent=2)

        via_lines.append(f"Account [{acc_name}]: " + "; ".join(cookie_kv_pairs[:8]))

    # Ghi DOLA_ALL_ACCOUNTS_COOKIES.json
    p_all = os.path.join(target_dir, "DOLA_ALL_ACCOUNTS_COOKIES.json")
    with open(p_all, "w", encoding="utf-8") as f:
        json.dump(multi_accounts, f, ensure_ascii=False, indent=2)

    # Ghi DOLA_ACCOUNTS_ARRAY.json
    p_arr = os.path.join(target_dir, "DOLA_ACCOUNTS_ARRAY.json")
    with open(p_arr, "w", encoding="utf-8") as f:
        json.dump(array_accounts, f, ensure_ascii=False, indent=2)

    # Ghi DOLA_COOKIE_STRINGS.txt
    p_txt = os.path.join(target_dir, "DOLA_COOKIE_STRINGS.txt")
    with open(p_txt, "w", encoding="utf-8") as f:
        f.write("\n\n".join(via_lines))

    log("API", f"✅ Đã xuất {len(multi_accounts)} tài khoản ra các tệp tại {target_dir}")
    return {
        "success": True,
        "count": len(multi_accounts),
        "files": [p_all, p_arr, p_txt, indiv_dir]
    }


@app.post("/api/accounts/update-bulk-cookies")
async def update_bulk_cookies(req: Request):
    """Cập nhật hàng loạt cookies tài khoản từ Extension vào Tool."""
    from session_store import SessionStore
    ss = SessionStore()
    ss.load()
    account_manager.load()

    try:
        body = await req.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Chuẩn hóa body: có thể là dict profiles {"acc1": {...}}, hoặc list [{"name": "acc1", ...}], hoặc {"profiles": ...}
    profiles_data = body.get("profiles", body) if isinstance(body, dict) else body

    updated_names = []

    if isinstance(profiles_data, dict):
        items = profiles_data.items()
    elif isinstance(profiles_data, list):
        items = [(item.get("name", f"acc_{idx}"), item) for idx, item in enumerate(profiles_data)]
    else:
        raise HTTPException(status_code=400, detail="Cấu trúc dữ liệu không hợp lệ.")

    for name, val in items:
        name = str(name).strip()
        if not name:
            continue

        cookies = []
        ls = {}
        fb_uid = ""
        cookie_string = ""

        if isinstance(val, list):
            cookies = val
        elif isinstance(val, dict):
            cookies = val.get("cookies", [])
            ls = val.get("local_storage", {})
            fb_uid = val.get("fb_uid", "")
            cookie_string = val.get("cookie_string", "")

        if not cookies and cookie_string:
            from session_store import parse_bulk_dola_cookies
            parsed = parse_bulk_dola_cookies(cookie_string, default_name=name)
            if parsed:
                cookies = parsed[0][1]

        if not cookies:
            continue

        # Lưu session
        ss.save_session(name, cookies, ls)

        # Cập nhật hoặc tạo mới account
        acc = account_manager.get_account(name)
        if not acc:
            login_type = "facebook" if fb_uid else "cookies"
            acc = account_manager.add_account(name=name, login_type=login_type, fb_uid=fb_uid, fb_cookies=cookie_string)
        acc.dola_session_saved = True
        acc.cookie_count = len(cookies)
        if fb_uid:
            acc.fb_uid = fb_uid
        if cookie_string:
            acc.fb_cookies = cookie_string

        updated_names.append(name)

    account_manager.save()
    log("API", f"✅ Đã cập nhật hàng loạt {len(updated_names)} tài khoản từ Extension.")
    return {
        "success": True,
        "updated_count": len(updated_names),
        "accounts": updated_names,
        "message": f"Đã cập nhật thành công {len(updated_names)} tài khoản vào Seedance Studio!"
    }


@app.post("/api/accounts/test-proxy")
async def test_proxy_for_account(account_name: str = Form(""), proxy_url: str = Form("")):
    """Test proxy cho account."""
    if proxy_url:
        result = await proxy_manager.test_proxy(proxy_url)
    elif account_name:
        acc = account_manager.get_account(account_name)
        if acc and acc.proxy:
            resolved = await proxy_manager.get_proxy_for_account(account_name, acc.proxy)
            if resolved:
                result = await proxy_manager.test_proxy(resolved)
            else:
                result = {"success": False, "error": "Cannot resolve proxy key"}
        else:
            result = {"success": False, "error": "No proxy configured"}
    else:
        result = {"success": False, "error": "No proxy provided"}
    return result


# ─── Profiles ─────────────────────────────────────────────────────────────────

@app.get("/api/profiles")
async def get_profiles():
    """Danh sách Chrome profiles."""
    profiles = []
    from config import CHROME_USER_DATA_BASE
    if os.path.isdir(CHROME_USER_DATA_BASE):
        for name in os.listdir(CHROME_USER_DATA_BASE):
            path = os.path.join(CHROME_USER_DATA_BASE, name)
            if os.path.isdir(path):
                profiles.append({
                    "name": name,
                    "path": path,
                    "running": browser_manager.is_chrome_running(name),
                })
    return {"profiles": profiles}

@app.post("/api/profiles/open")
async def open_profile(req: OpenProfileRequest):
    """Mở Chrome profile thủ công (kèm Extension & nạp Cookie FB nếu có)."""
    account_name = req.account_name
    acc = account_manager.get_account(account_name)

    # Lấy proxy nếu có
    proxy_url = req.proxy_url
    if not proxy_url and acc and acc.proxy:
        proxy_url = await proxy_manager.get_proxy_for_account(account_name, acc.proxy)

    fb_cookies = acc.fb_cookies if acc else ""

    try:
        pid = await browser_manager.launch_chrome_interactive(
            account_name, proxy_url=proxy_url, fb_cookies_str=fb_cookies
        )
        return {"success": True, "pid": pid, "account": account_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Proxy Pool ──────────────────────────────────────────────────────────────

@app.get("/api/proxy-pool")
async def get_proxy_pool():
    """Lấy cấu hình proxy pool."""
    return proxy_manager.get_pool_info()

@app.post("/api/proxy-pool")
async def update_proxy_pool(req: ProxyPoolRequest):
    """Cập nhật proxy pool."""
    proxy_manager.update_pool(
        proxies=req.proxies,
        carrier=req.carrier,
        province=req.province,
        enabled=req.enabled,
        source=req.source,
        custom_proxies=req.custom_proxies,
        vpn_auto_rotate=req.vpn_auto_rotate,
    )
    return {"success": True, "info": proxy_manager.get_pool_info()}

@app.get('/api/proxy/rotation-status')
async def get_proxy_rotation_status():
    import asyncio
    from config import PROXY_POOL_FILE
    from utils import safe_json_load
    from vpn_rotation_client import sync_rotation
    return await asyncio.to_thread(sync_rotation, safe_json_load(PROXY_POOL_FILE, {}))

@app.post("/api/proxy/toggle")
async def toggle_proxy_mode(req: Request):
    """Bật/tắt nhanh chế độ proxy hoặc thay đổi nguồn proxy."""
    try:
        body = await req.json()
    except Exception:
        body = {}
    if "enabled" in body:
        proxy_manager.pool.enabled = bool(body["enabled"])
    if "source" in body:
        proxy_manager.pool.source = str(body["source"])
    proxy_manager.save()
    status_str = "BẬT" if proxy_manager.pool.enabled else "TẮT"
    log("Proxy", f"Chuyển đổi Proxy: [{status_str}] | Nguồn: {proxy_manager.pool.source}")
    return {"success": True, "enabled": proxy_manager.pool.enabled, "source": proxy_manager.pool.source}

@app.get("/api/proxy/active-vpn-list")
async def get_active_vpn_list():
    """Lấy danh sách các cổng proxy đang hoạt động từ Tool Proxy VPN."""
    from proxy_manager import import_from_ocproxy_hub
    proxies = import_from_ocproxy_hub()
    res = []
    if proxies:
        for p in proxies:
            port = p.get("port")
            user = p.get("auth_user", "admin")
            pass_ = p.get("auth_pass", "admin123")
            country = p.get("country_name", "VPN")
            flag = p.get("flag", "🌐")
            ip = p.get("real_wan_ip", "")
            raw = f"127.0.0.1:{port}:{user}:{pass_}" if user and pass_ else f"127.0.0.1:{port}"
            label = f"{flag} Cổng {port} - {country} (IP: {ip or 'Online'})"
            res.append({
                "port": port,
                "host": "127.0.0.1",
                "user": user,
                "pass": pass_,
                "country": country,
                "raw": raw,
                "label": label,
                "scheme": "http"
            })
    return {"success": True, "total": len(res), "proxies": res}

@app.get("/api/proxy/account-proxy/{account_name}")
async def get_account_proxy(account_name: str):
    """Lấy proxy được cấu hình riêng cho tài khoản (nếu trống tự cấp từ pool VPN)."""
    acc = account_manager.get_account(account_name)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    
    proxy_str = acc.proxy or acc.proxy_direct
    if not proxy_str and proxy_manager.pool.proxies:
        proxy_str = await proxy_manager.get_proxy_for_account(account_name)
        if proxy_str:
            acc.proxy = proxy_str
            account_manager.save()

    return {
        "success": True,
        "account_name": account_name,
        "proxy": proxy_str or "",
    }

@app.post("/api/proxy/set-account-proxy")
async def set_account_proxy(req: AccountProxyRequest):
    """Lưu proxy cho tài khoản từ Extension hoặc GUI."""
    acc = account_manager.get_account(req.account_name)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    acc.proxy = req.proxy.strip()
    account_manager.save()
    log("Proxy", f"Đã cập nhật proxy cho tài khoản {req.account_name}")
    return {"success": True, "account_name": req.account_name, "proxy": acc.proxy}


# ─── Video Generation ────────────────────────────────────────────────────────

@app.post("/api/text-to-video")
async def text_to_video(req: CreateVideoRequest):
    """Tạo video từ text prompt."""
    job = job_manager.create_job(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        mode=req.mode,
        duration_target=req.duration_target,
        model_version=req.model_version,
        enable_upscale=req.enable_upscale,
        upscale_target=req.upscale_target,
        image_path=req.image_path,
    )
    job_manager.start_job(job.id)
    return {"success": True, "job_id": job.id, "job": job.to_dict()}

@app.post("/api/image-to-video")
async def image_to_video(req: CreateVideoRequest):
    """Tạo video từ ảnh + prompt (alias cho text-to-video với image_path)."""
    job = job_manager.create_job(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        mode=req.mode,
        duration_target=req.duration_target,
        model_version=req.model_version,
        enable_upscale=req.enable_upscale,
        upscale_target=req.upscale_target,
        image_path=req.image_path,
    )
    job_manager.start_job(job.id)
    return {"success": True, "job_id": job.id, "job": job.to_dict()}


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Polling trạng thái job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Hủy job."""
    ok = job_manager.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found or already finished")
    return {"success": True}

@app.get("/api/jobs")
async def list_jobs():
    """Danh sách tất cả jobs."""
    return {"jobs": job_manager.get_all_jobs()}


# ─── Videos ───────────────────────────────────────────────────────────────────

@app.get("/api/list-videos")
async def list_videos():
    """Danh sách video đã tạo."""
    return {"videos": video_downloader.list_output_videos()}

@app.get("/api/output-folder")
async def get_output_folder():
    """Đường dẫn thư mục output."""
    return {"path": OUTPUT_DIR}

@app.post("/api/open-folder")
async def open_folder(path: str = Form(OUTPUT_DIR)):
    """Mở thư mục trong Explorer."""
    import subprocess
    try:
        subprocess.Popen(["explorer", os.path.normpath(path)])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── File Upload ──────────────────────────────────────────────────────────────

@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload ảnh tham chiếu."""
    file_id = generate_upload_id()
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    return {
        "success": True,
        "filename": filename,
        "path": filepath,
        "url": f"/uploads/{filename}",
    }

@app.post("/api/save_bypass_image")
async def save_bypass_image(file: UploadFile = File(...)):
    """Lưu ảnh bypass captcha."""
    bypass_id = generate_bypass_id()
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{bypass_id}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    return {
        "success": True,
        "filename": filename,
        "url": f"/uploads/{filename}",
    }


# ─── Output Videos (serve files) ─────────────────────────────────────────────

@app.get("/output_videos/{filename}")
async def serve_output_video(filename: str):
    """Phục vụ file video output."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.isfile(filepath):
        return FileResponse(filepath, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")


# ─── License ──────────────────────────────────────────────────────────────────

@app.get("/api/license")
async def get_license():
    """Trạng thái license."""
    from config import LICENSE_STATE_FILE
    from utils import safe_json_load
    data = safe_json_load(LICENSE_STATE_FILE, {})
    return {
        "device_id": get_device_id(),
        "license_key": data.get("license_key", ""),
        "activated": data.get("activated", True),
        "expires_at": data.get("expires_at", ""),
    }

@app.post("/api/license")
async def activate_license(req: LicenseRequest):
    """Kích hoạt license key."""
    from config import LICENSE_STATE_FILE
    from utils import safe_json_save
    data = {
        "license_key": req.license_key,
        "device_id": get_device_id(),
        "activated": True,
        "activated_at": get_timestamp(),
    }
    safe_json_save(LICENSE_STATE_FILE, data)
    return {"success": True, "activated": True}

@app.get("/api/license/verify")
async def verify_license():
    """Xác thực license."""
    return {"valid": True, "device_id": get_device_id()}


# ─── Facebook Cookie Injection ───────────────────────────────────────────────

@app.post("/api/inject-facebook-cookie")
async def inject_facebook_cookie(request: Request):
    """Nạp cookie VIA Facebook vào Profile Chrome qua CDP/Playwright."""
    account_name = ""
    cookies_str = ""

    # Parse JSON hoặc Form data linh hoạt
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            account_name = data.get("account_name", "")
            cookies_str = data.get("cookies", "")
        else:
            form = await request.form()
            account_name = form.get("account_name", "")
            cookies_str = form.get("cookies", "")
    except Exception:
        pass

    if not account_name:
        accs = account_manager.accounts
        account_name = accs[0].name if accs else "fb01"

    acc = account_manager.get_account(account_name)
    if not acc:
        acc = account_manager.add_account(account_name, login_type="facebook")

    acc.fb_cookies = cookies_str
    account_manager.save()

    # Nạp trực tiếp vào Chrome nếu session đang mở
    count = await browser_manager.inject_facebook_cookies(account_name, cookies_str)

    return {
        "success": True,
        "count": count,
        "account": account_name,
        "message": f"Đã nạp {count} cookie Facebook vào profile '{account_name}'"
    }


# ─── Import asyncio (needed by some routes) ──────────────────────────────────
import asyncio

# Local GUI command: queue through Qt instead of spawning unrelated browsers.
gui_open_accounts_handler = None


class OpenStudioAccountsRequest(BaseModel):
    accounts: list[str]


@app.post('/api/studio/open-accounts')
async def open_studio_accounts(body: OpenStudioAccountsRequest, request: Request):
    if not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Local tool command only')
    origin = request.headers.get('origin')
    if origin and origin not in (f'http://127.0.0.1:{API_PORT}', f'http://localhost:{API_PORT}'):
        raise HTTPException(403, 'Untrusted origin')
    names = list(dict.fromkeys(body.accounts))
    if not names or len(names) > 10:
        raise HTTPException(400, 'Choose 1–10 saved accounts')
    if gui_open_accounts_handler is None:
        raise HTTPException(503, 'Studio GUI is not connected')
    account_manager.load()
    if any(account_manager.get_account(name) is None for name in names):
        raise HTTPException(404, 'Unknown saved account')
    gui_open_accounts_handler(names)
    return {'queued': True, 'accounts': names, 'launcher': 'Studio GUI'}
