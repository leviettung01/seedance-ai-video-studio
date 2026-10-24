"""
Script kiểm tra toàn diện tất cả các session tài khoản hiện có trong hệ thống:
1. Đăng nhập / nạp cookie từng tài khoản
2. Truy cập https://www.dola.com/chat/create-image và https://www.dola.com/chat/
3. Kiểm tra thông tin User Name, Trạng thái Login, Điểm/Credits còn lại
"""
import asyncio, sys, os, json
sys.path.insert(0, r"f:\Seedance\seedance_ai_video_studio_src")
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from browser_manager import BrowserManager

async def check_all_accounts_credit():
    bm = BrowserManager()
    
    with open(r'C:\Users\ADMIN\.seedance_ai_video_studio\accounts_sessions.json', 'r', encoding='utf-8') as f:
        sessions = json.load(f)
    
    account_names = list(sessions.keys())
    print(f"🔍 Tìm thấy {len(account_names)} tài khoản trong sessions: {account_names}")
    
    results = {}
    
    for i, acc_name in enumerate(account_names):
        wid = 800 + i
        print(f"\n==========================================")
        print(f"[{i+1}/{len(account_names)}] Kiểm tra tài khoản: '{acc_name}' (Worker {wid})")
        print(f"==========================================")
        
        try:
            port = await bm.launch_temp_chrome(worker_id=wid, show_browser=True)
            browser = await bm.connect_worker(wid)
            page = browser.contexts[0].pages[0]
            
            # Inject session
            await bm.inject_session_to_worker(wid, acc_name)
            await page.goto("https://www.dola.com/chat/create-image", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(4)
            
            # Dismiss overlays
            for sel in ['button:has-text("OK")', 'button:has-text("Got it")', 'button:has-text("Đồng ý")', '[aria-label="close"]']:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible(): await el.click()
                except: pass
            await asyncio.sleep(1)
            
            # Get Page text and user info
            user_info = await page.evaluate("""() => {
                // Find avatar / username
                const avatar = document.querySelector('[class*="avatar"], [class*="user"], [class*="profile"]');
                const text = document.body.innerText || '';
                
                const isGuest = text.includes('Người dùng khách') || text.includes('Đăng nhập');
                const isQuotaExhausted = text.includes('đạt giới hạn') || text.includes('0 điểm');
                
                // Find any credit numbers
                const spans = Array.from(document.querySelectorAll('span, div, p, button')).map(e => e.textContent.trim()).filter(t => t.length < 80);
                const creditSpans = spans.filter(t => t.includes('điểm') || t.includes('credit') || t.includes('tín dụng') || t.includes('lượt'));
                
                // Check if Video tab is present
                const hasVideoTab = !!Array.from(document.querySelectorAll('button, [role="tab"]')).find(e => (e.textContent || '').trim() === 'Video');
                
                return {
                    isGuest,
                    isQuotaExhausted,
                    hasVideoTab,
                    creditSpans: creditSpans.slice(0, 5),
                    snippet: text.substring(0, 300)
                };
            }""")
            
            # Take screenshot for record
            ss_path = rf"C:\Users\ADMIN\.gemini\antigravity-ide\brain\267e0be2-2822-4ba8-9b68-68d61b0c84ed\check_acc_{acc_name}.png"
            await page.screenshot(path=ss_path)
            
            status = "UNKNOWN"
            if user_info['isGuest'] and not user_info['hasVideoTab']:
                status = "❌ NOT LOGGED IN / GUEST"
            elif user_info['isQuotaExhausted']:
                status = "⚠️ QUOTA EXHAUSTED (0 ĐIỂM)"
            elif user_info['hasVideoTab']:
                status = "✅ LOGGED IN & CÓ THỂ TẠO VIDEO"
            
            results[acc_name] = {
                "status": status,
                "details": user_info
            }
            print(f"  → Kết quả: {status}")
            if user_info['creditSpans']:
                print(f"  → Credits info: {user_info['creditSpans']}")
                
            await bm.cleanup_worker(wid)
        except Exception as e:
            print(f"  ❌ Lỗi kiểm tra {acc_name}: {e}")
            try: await bm.cleanup_worker(wid)
            except: pass
            results[acc_name] = {"status": f"ERROR: {e}"}
            
    print("\n\n" + "=" * 60)
    print("📊 TỔNG HỢP TRẠNG THÁI TẤT CẢ TÀI KHOẢN")
    print("=" * 60)
    for acc, data in results.items():
        print(f"• {acc:20}: {data['status']}")
    
if __name__ == '__main__':
    asyncio.run(check_all_accounts_credit())
