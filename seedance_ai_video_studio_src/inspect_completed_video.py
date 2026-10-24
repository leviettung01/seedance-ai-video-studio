import asyncio, sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9250')
        page = browser.contexts[0].pages[0]
        
        # 1. Performance network entries
        perf_urls = await page.evaluate("""
            (() => {
                return performance.getEntriesByType('resource')
                    .map(r => r.name)
                    .filter(n => (n.includes('tos-') || n.includes('video') || n.includes('.mp4') || n.includes('byte') || n.includes('lr=')) && !n.endsWith('.js') && !n.endsWith('.css'));
            })()
        """)
        print('1. Performance Video Network URLs:', json.dumps(perf_urls, indent=2))
        
        # 2. Check all video tags and sources in DOM
        media = await page.evaluate("""
            (() => {
                const results = [];
                document.querySelectorAll('video').forEach(v => {
                    results.push({ tag: 'video', src: v.src, currentSrc: v.currentSrc, poster: v.poster });
                });
                document.querySelectorAll('source').forEach(s => {
                    results.push({ tag: 'source', src: s.src });
                });
                document.querySelectorAll('a').forEach(a => {
                    if (a.href && (a.href.includes('tos') || a.href.includes('video') || a.href.includes('mp4'))) {
                        results.push({ tag: 'a', href: a.href });
                    }
                });
                return results;
            })()
        """)
        print('2. DOM Media elements:', json.dumps(media, indent=2))
        
        # 3. Check localStorage
        ls = await page.evaluate("""
            (() => {
                return {
                    seedance: localStorage.getItem('__seedanceLinks'),
                    dola: localStorage.getItem('__dolaWatermarkLinks'),
                    allKeys: Object.keys(localStorage)
                };
            })()
        """)
        print('3. LocalStorage keys and captured links:', json.dumps(ls, indent=2))

if __name__ == '__main__':
    asyncio.run(inspect())
