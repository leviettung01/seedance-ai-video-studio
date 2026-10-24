"""
Monitor ALL fetch requests on the live page to see what URL/body Dola sends.
Installs a real-time fetch listener.
"""
import asyncio, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def monitor():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9258')
        page = browser.contexts[0].pages[0]
        
        # Install a real-time fetch monitor
        await page.evaluate("""
            (() => {
                if (window.__fetchMonitorInstalled) return;
                window.__fetchMonitorInstalled = true;
                window.__fetchLog = [];
                
                const currentFetch = window.fetch;
                window.fetch = async function(input, init) {
                    let url = '';
                    try { url = typeof input === 'string' ? input : (input && input.url) || ''; } catch(e) {}
                    
                    const logEntry = {
                        ts: Date.now(),
                        url: url.substring(0, 150),
                        method: init?.method || 'GET',
                        bodyType: typeof init?.body,
                        bodyLen: (init?.body || '').length,
                        bodyPreview: typeof init?.body === 'string' ? init.body.substring(0, 300) : 'non-string',
                        hasDuration: typeof init?.body === 'string' ? init.body.includes('duration') : false,
                        isTargetUrl: url.indexOf('/chat/completion') >= 0 || url.indexOf('/im/message') >= 0 || url.indexOf('/im/chain') >= 0,
                    };
                    
                    window.__fetchLog.push(logEntry);
                    if (window.__fetchLog.length > 100) window.__fetchLog.shift();
                    
                    // Console log for visibility
                    if (logEntry.hasDuration || logEntry.isTargetUrl) {
                        console.log('[FETCH MONITOR]', JSON.stringify(logEntry));
                    }
                    
                    return currentFetch.apply(this, arguments);
                };
                console.log('[FETCH MONITOR] Installed');
            })()
        """)
        
        print("Fetch monitor installed. Waiting 30s to collect requests...")
        await asyncio.sleep(30)
        
        logs = await page.evaluate("window.__fetchLog || []")
        print(f"\n=== {len(logs)} fetch requests captured ===\n")
        for log in logs:
            if log.get('hasDuration') or log.get('isTargetUrl') or 'chat' in log.get('url', '').lower():
                print(json.dumps(log, indent=2, ensure_ascii=False))
                print("---")
        
        # Also print non-target requests summary
        print(f"\n=== All {len(logs)} requests (URL only) ===")
        for log in logs:
            print(f"  {log.get('method')} {log.get('url')} (body={log.get('bodyType')}, len={log.get('bodyLen')})")

asyncio.run(monitor())
