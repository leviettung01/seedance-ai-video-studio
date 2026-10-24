import json
import os
import sys

sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8')
from session_store import SessionStore
from account_manager import AccountManager

RAW_COOKIES_JSON = """[
  {
    "domain": "www.dola.com",
    "expirationDate": 1819555710,
    "hostOnly": true,
    "httpOnly": false,
    "name": "i18next",
    "path": "/",
    "sameSite": "strict",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "vi"
  },
  {
    "domain": "www.dola.com",
    "expirationDate": 1822322692,
    "hostOnly": true,
    "httpOnly": false,
    "name": "dbx-web-theme",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "light"
  },
  {
    "domain": ".www.dola.com",
    "expirationDate": 1819298693,
    "hostOnly": false,
    "httpOnly": false,
    "name": "flow_user_country",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "VN"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946679.921703,
    "hostOnly": false,
    "httpOnly": false,
    "name": "passport_csrf_token",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "43a8ed97dc5aca774c9b4d6ee2fda32a"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946679.921785,
    "hostOnly": false,
    "httpOnly": false,
    "name": "passport_csrf_token_default",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "43a8ed97dc5aca774c9b4d6ee2fda32a"
  },
  {
    "domain": "www.dola.com",
    "expirationDate": 1795538689,
    "hostOnly": true,
    "httpOnly": false,
    "name": "msToken",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "xiFjxMG7zfROyD6EbP-JJEa2KVmNW3YEW_Fc77yUJ0FLjhQ7Iu83cJYMbSDLgkbi47n6hY0UUzTf3UFShf1S5pID_-GbScBb-TuXCoEB_udwhChWlrsVqA=="
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1819298689.588751,
    "hostOnly": false,
    "httpOnly": true,
    "name": "odin_tt",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "4f5f4bff03134f07b23bc42c24e1bb3f7b72a05e8745466b7b971b800e322a40efed7bb5d4dc33d89fdffcd13f27fbf5e42432d3cd873c528764e1fcf39f25a1"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1790354689.588797,
    "hostOnly": false,
    "httpOnly": true,
    "name": "passport_auth_status",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "861e891b2dfbd923bf9790ddfd36f855%2C"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1790354689.588828,
    "hostOnly": false,
    "httpOnly": true,
    "name": "passport_auth_status_ss",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "861e891b2dfbd923bf9790ddfd36f855%2C"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1818866689.588849,
    "hostOnly": false,
    "httpOnly": true,
    "name": "sid_guard",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "a21f58c97276f3ca5c915b2fc122cc66%7C1787762690%7C5184000%7CSun%2C+25-Oct-2026+16%3A44%3A50+GMT"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588869,
    "hostOnly": false,
    "httpOnly": true,
    "name": "uid_tt",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "6f77d7beb12e21cff94e3d45fddd78c457a84e5ed63dfad9d48d5e30c96802bc"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588886,
    "hostOnly": false,
    "httpOnly": true,
    "name": "uid_tt_ss",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "6f77d7beb12e21cff94e3d45fddd78c457a84e5ed63dfad9d48d5e30c96802bc"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588904,
    "hostOnly": false,
    "httpOnly": true,
    "name": "sid_tt",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "a21f58c97276f3ca5c915b2fc122cc66"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588922,
    "hostOnly": false,
    "httpOnly": true,
    "name": "sessionid",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "a21f58c97276f3ca5c915b2fc122cc66"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.58894,
    "hostOnly": false,
    "httpOnly": true,
    "name": "sessionid_ss",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "a21f58c97276f3ca5c915b2fc122cc66"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588957,
    "hostOnly": false,
    "httpOnly": true,
    "name": "has_biz_token",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "false"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588976,
    "hostOnly": false,
    "httpOnly": true,
    "name": "sid_ucp_v1",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "1.0.0-KDQ4Nzk1NDU0Y2E2ZWNkZmMwOWM4NzZjYzkxM2MyOWRhNTBlYWQ3ZGYKIAi1iOD8-t7Ex2oQgrC81AYYt6AeIAww9K-81AY4CEASEAMaA215YSIgYTIxZjU4Yzk3Mjc2ZjNjYTVjOTE1YjJmYzEyMmNjNjY"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1792946689.588995,
    "hostOnly": false,
    "httpOnly": true,
    "name": "ssid_ucp_v1",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "1.0.0-KDQ4Nzk1NDU0Y2E2ZWNkZmMwOWM4NzZjYzkxM2MyOWRhNTBlYWQ3ZGYKIAi1iOD8-t7Ex2oQgrC81AYYt6AeIAww9K-81AY4CEASEAMaA215YSIgYTIxZjU4Yzk3Mjc2ZjNjYTVjOTE1YjJmYzEyMmNjNjY"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1819298689.58902,
    "hostOnly": false,
    "httpOnly": true,
    "name": "store-idc",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "mya"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1819298689.589037,
    "hostOnly": false,
    "httpOnly": true,
    "name": "store-country-code",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "vn"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1819298689.589052,
    "hostOnly": false,
    "httpOnly": true,
    "name": "store-country-code-src",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "uid"
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1790354692,
    "hostOnly": false,
    "httpOnly": false,
    "name": "flow_cur_user_sec_id",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "Kz9bAGEdJCBsLCAyMVkKPho/GixPXUgADx8CQWYQNVpMLxdLLUQPHhoSESNIWTEfMilcGUU5DDV7BQYqXhsROR0zGgUbCSQOXh44Tg=="
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1790354689,
    "hostOnly": false,
    "httpOnly": false,
    "name": "flow_multi_user_sec_info",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "Kz9bAGEdJCBsLCAyMVkKPho/GixPXUgADx8CQWYQNVpMLxdLLUQPHhoSESNIWTEfMilcGUU5DDV7BQYqXhsROR0zGgUbCSQOXh44ThcQCg1KAQRJWhpbRU5GRlkVUlBAVQ=="
  },
  {
    "domain": "www.dola.com",
    "expirationDate": 1788588998.002405,
    "hostOnly": true,
    "httpOnly": true,
    "name": "gd_random",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "eyJwZXJjZW50IjowLjI2NDI2OTM1MTExNTgyOTk0LCJtYXRjaCI6ZmFsc2V9.tEijOJmtS8FhYKDVZ2sTSaYWcDkqOBf/MpRjAEAqBDw="
  },
  {
    "domain": ".dola.com",
    "expirationDate": 1819123710.605741,
    "hostOnly": false,
    "httpOnly": true,
    "name": "ttwid",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "1%7CHjzLTU6zJgUe26OJQA9uiOKXCkuwqPL3Ns6txc2V7KU%7C1788019710%7C63f3ce3030652193af31e68af9f933432a492558a234af2cb837a3340580a30d"
  }
]"""

def main():
    cookies_list = json.loads(RAW_COOKIES_JSON)
    ss = SessionStore()
    
    # 1. Update session in SessionStore (accounts_sessions.json)
    local_storage = {
        "__dolaDur31": "1",
        "__dolaDurBypass": "1",
        "__dolaTargetDur": "31",
        "i18nextLng": "vi",
        "dbx-web-theme": "light"
    }
    
    ss.save_session("leviettung05", cookies_list, local_storage)
    ss.save()
    print("✅ Đã cập nhật thành công session 'leviettung05' vào SessionStore!")
    
    # 2. Update accounts state in AccountManager (accounts_state.json)
    am = AccountManager()
    acc = am.get_account("leviettung05")
    if not acc:
        am.add_account("leviettung05", proxy="")
    am.update_account("leviettung05", status="active", login_status="logged_in")
    print("✅ Đã cập nhật trạng thái 'leviettung05' thành 'active' (logged_in) trong AccountManager!")
    
    # In thông tin kiểm tra
    sess = ss.load_session("leviettung05")
    if sess:
        cookies_saved, ls_saved = sess
        print(f"📊 Session summary for 'leviettung05':")
        print(f"   Cookies count: {len(cookies_saved)}")
        print(f"   LocalStorage keys: {len(ls_saved)}")
        print(f"   Has session: {ss.has_session('leviettung05')}")

if __name__ == "__main__":
    main()
