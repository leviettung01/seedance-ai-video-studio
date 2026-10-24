import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
data_dir = r'C:\Users\ADMIN\.seedance_ai_video_studio'
for f in os.listdir(data_dir):
    if f.endswith('.json'):
        print(f'{f}: {os.path.getsize(os.path.join(data_dir, f))} bytes')
acc_file = os.path.join(data_dir, 'accounts_state.json')
if os.path.exists(acc_file):
    with open(acc_file, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
        for acc in d.get('accounts', []):
            print(f"  - {acc['name']}: status={acc.get('status')}, login={acc.get('login_status')}")
