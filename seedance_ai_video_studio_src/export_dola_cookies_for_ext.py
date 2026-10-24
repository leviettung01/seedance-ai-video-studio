import os
import sys
import json
import time

sys.path.insert(0, 'f:/Seedance/seedance_ai_video_studio_src')
from session_store import SessionStore
from account_manager import AccountManager

ss = SessionStore()
ss.load()
am = AccountManager()
am.load()

target_dir = 'F:/Seedance'
indiv_dir = os.path.join(target_dir, 'Dola_Account_Cookies_Individual')
os.makedirs(indiv_dir, exist_ok=True)

multi_accounts = {}
array_accounts = []
extension_multi_profiles = {}
via_lines = []

colors = ['#ff7e00', '#2563eb', '#10b981', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316']

for idx, (acc_name, sdata) in enumerate(ss._sessions.items()):
    raw_cookies = sdata.get('cookies', [])
    clean_cookies = []
    cookie_kv_pairs = []
    for c in raw_cookies:
        c_dict = {
            'name': str(c.get('name', '')).strip(),
            'value': str(c.get('value', '')).strip(),
            'domain': str(c.get('domain', '.dola.com')),
            'path': str(c.get('path', '/')),
            'secure': bool(c.get('secure', True)),
            'httpOnly': bool(c.get('httpOnly', False)),
            'sameSite': str(c.get('sameSite', 'Lax'))
        }
        if 'expirationDate' in c:
            c_dict['expirationDate'] = c['expirationDate']
        elif 'expires' in c:
            c_dict['expirationDate'] = c['expires']
        clean_cookies.append(c_dict)
        cookie_kv_pairs.append(f"{c_dict['name']}={c_dict['value']}")

    acc = am.get_account(acc_name)
    fb_uid = (acc.fb_uid if acc else '') or sdata.get('fb_uid', '')
    dola_uid = (acc.dola_uid if acc else '') or sdata.get('dola_uid', '')
    ls = sdata.get('local_storage', {})

    multi_accounts[acc_name] = clean_cookies
    array_accounts.append({
        'name': acc_name,
        'cookies': clean_cookies,
        'local_storage': ls,
        'fb_uid': fb_uid,
        'dola_uid': dola_uid
    })

    extension_multi_profiles[acc_name] = {
        'name': acc_name,
        'cookies': clean_cookies,
        'local_storage': ls,
        'cookie_string': '; '.join(cookie_kv_pairs),
        'fb_uid': fb_uid,
        'dola_uid': dola_uid,
        'color': colors[idx % len(colors)],
        'updated_at': int(time.time() * 1000)
    }

    safe_fname = acc_name.replace(' ', '_').replace('/', '_').replace('\\', '_') + '.json'
    with open(os.path.join(indiv_dir, safe_fname), 'w', encoding='utf-8') as f:
        json.dump(clean_cookies, f, ensure_ascii=False, indent=2)

    via_lines.append(f'Account [{acc_name}]: ' + '; '.join(cookie_kv_pairs[:8]))

p_all = os.path.join(target_dir, 'DOLA_ALL_ACCOUNTS_COOKIES.json')
with open(p_all, 'w', encoding='utf-8') as f:
    json.dump(extension_multi_profiles, f, ensure_ascii=False, indent=2)

p_arr = os.path.join(target_dir, 'DOLA_ACCOUNTS_ARRAY.json')
with open(p_arr, 'w', encoding='utf-8') as f:
    json.dump(array_accounts, f, ensure_ascii=False, indent=2)

p_txt = os.path.join(target_dir, 'DOLA_COOKIE_STRINGS.txt')
with open(p_txt, 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(via_lines))

print(f"Successfully exported {len(multi_accounts)} accounts to {target_dir}")
for k, v in multi_accounts.items():
    print(f"  + {k}: {len(v)} cookies")
