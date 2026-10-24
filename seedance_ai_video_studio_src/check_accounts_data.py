import os
import json

sessions_file = os.path.expanduser('~/.seedance_ai_video_studio/accounts_sessions.json')
state_file = os.path.expanduser('~/.seedance_ai_video_studio/accounts_state.json')

print("=== 1. SESSIONS FILE ===")
sessions = {}
if os.path.exists(sessions_file):
    with open(sessions_file, 'r', encoding='utf-8') as f:
        sessions = json.load(f)
    print(f"Total sessions: {len(sessions)}")
    for k, v in sessions.items():
        cookies = v.get('cookies', [])
        ls = v.get('local_storage', {})
        print(f"  Account: {k} -> {len(cookies)} cookies, {len(ls)} localStorage keys")
else:
    print("sessions_file not found")

print("\n=== 2. STATE FILE ===")
state = []
if os.path.exists(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f"Total state accounts: {len(state)}")
    for acc in state:
        name = acc.get('name')
        ltype = acc.get('login_type')
        uid = acc.get('fb_uid')
        fb_c = acc.get('fb_cookies', '')
        print(f"  Account: {name} | Type: {ltype} | UID: {uid} | Cookie length: {len(fb_c)}")
else:
    print("state_file not found")
