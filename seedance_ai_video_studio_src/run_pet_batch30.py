"""Resumeable batch using Studio GUI profiles, native Skill and extension downloads."""
import asyncio, json, re, time, hashlib
from pathlib import Path
from urllib.parse import urlsplit, unquote
import httpx
from playwright.async_api import async_playwright
from browser_manager import BrowserManager
from account_manager import AccountManager
from fb_login_automation import FBLoginAutomation
from native_video_automation import NativeVideoAutomation
from video_downloader import VideoDownloader

SOURCE = Path(r'D:\SKILL VIDEO\Timelapse Phòng thú cưng\10_prompt_timelapse_thi_cong_phong_thu_cung_vip.md')
OUT = Path(r'D:\Seedance\output_videos\pet_room_batch30_20261022')
OUT.mkdir(parents=True, exist_ok=True)

def record(kind, **data):
    row = dict(time=time.time(), event=kind, **data)
    with (OUT/'manifest.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False)+'\n')
    print(json.dumps(row, ensure_ascii=True), flush=True)

async def run_pair(name, numbered):
    async with httpx.AsyncClient(trust_env=False, timeout=20) as http:
        r=await http.post('http://127.0.0.1:8899/api/studio/open-accounts', json={'accounts':[name]})
        r.raise_for_status()
        pool=(await http.get('http://127.0.0.1:8899/api/proxy-pool')).json()
    if not pool.get('enabled') or pool.get('source')!='vpn_tool' or not pool.get('proxies'):
        raise RuntimeError('France VPN2Proxy pool is not enabled; no direct fallback')
    u=urlsplit(pool['proxies'][0])
    cfg=dict(enabled=True, host=u.hostname, port=u.port, scheme='http',
             username=unquote(u.username or ''), password=unquote(u.password or ''),source='vpn_tool',account_name=name)
    async with async_playwright() as pw:
        browser=None
        for _ in range(90):
            try:
                port=BrowserManager()._get_port(name)
                browser=await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=3000)
                break
            except Exception:
                await asyncio.sleep(2)
        if browser is None: raise RuntimeError('Studio profile did not open')
        context=browser.contexts[0]
        worker=next((w for w in context.service_workers if 'gaonpmkdcbhbfakicboldjnbijnbdbgo' in w.url),None)
        if worker is None: raise RuntimeError('Dola extension service worker is not ready')
        cfg.update(source='vpn_tool',raw_proxy=f"{u.hostname}:{u.port}:{unquote(u.username or '')}:{unquote(u.password or '')}",account_name=name)
        synced=await worker.evaluate('''cfg=>new Promise(resolve=>{
          chrome.storage.local.set({dola_proxy_config:cfg,dola_proxy_enabled:true,
            dola_proxy_auth:{username:cfg.username,password:cfg.password},dola_vpn_auto_rotate:true},
            ()=>resolve(!chrome.runtime.lastError));
        })''',cfg)
        if not synced: raise RuntimeError('Could not synchronize current VPN2Proxy credentials into the extension')
        rotation={}
        for _ in range(10):
            await asyncio.sleep(2)
            rotation=await worker.evaluate("async()=>{let x=await chrome.storage.local.get('dola_rotation_status');return x.dola_rotation_status||{}}")
            if rotation.get('enabled') and rotation.get('success'):
                break
        if not rotation.get('enabled') or not rotation.get('success'):
            raise RuntimeError('The extension has not confirmed its shared five-minute VPN2Proxy rotation lease')
        check=await context.new_page()
        try:
            country=None
            for attempt in range(12):
                try:
                    await check.goto('https://ipinfo.io/json',wait_until='domcontentloaded',timeout=20000)
                    country=json.loads((await check.locator('body').inner_text()).strip()).get('country')
                    break
                except Exception:
                    record('proxy_reconnecting',account=name,attempt=attempt+1)
                    await asyncio.sleep(10)
            if country!='FR': raise RuntimeError('Proxy country is not France')
        finally:
            await check.close()
        page=next((p for p in context.pages if 'dola.com/chat' in p.url),None)
        if not page: page=await context.new_page()
        await page.goto('https://www.dola.com/chat/',wait_until='domcontentloaded')
        if not await FBLoginAutomation().fetch_dola_account_info(context):
            raise RuntimeError('LOGIN_REQUIRED: no active Dola account')
        await asyncio.sleep(5)
        cdp=await context.new_cdp_session(page)
        await cdp.send('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(OUT),'eventsEnabled':True})
        record('profile_ready', account=name, country=country, prompts=[n for n,_ in numbered])
        native=NativeVideoAutomation()
        assignment=OUT/f'{name}_prompts_{numbered[0][0]:02d}_{numbered[-1][0]:02d}.txt'
        assignment.write_text('\n\n'.join(f'PROMPT {n:02d}\n{p}' for n,p in numbered),encoding='utf-8')
        async def found(item):
            n=item['prompt_number']
            record('render_returned',account=name,prompt=n)
            prefix=f'prompt_{n:02d}_{name}_'
            for _ in range(180):
                files=[f for f in OUT.glob(prefix+'*.mp4') if f.stat().st_size>0 and not Path(str(f)+'.crdownload').exists()]
                if files:
                    path=max(files,key=lambda p:p.stat().st_mtime)
                    info=await asyncio.to_thread(VideoDownloader.get_video_info,str(path))
                    if not info.get('width'): raise RuntimeError('Invalid downloaded video')
                    record('downloaded',account=name,prompt=n,path=str(path),duration=info.get('duration'),via='extension')
                    return
                await asyncio.sleep(2)
            raise RuntimeError(f'EXTENSION_DOWNLOAD_PENDING: prompt {n}; do not resubmit generation')
        try:
            await native.execute_skill_batch(page,[p for _,p in numbered],account_name=name,
                aspect_ratio='9:16',model_version='2.5',prompt_numbers=[n for n,_ in numbered],
                batch_id=OUT.name,job_id=name,auto_confirm=True,on_video_found=found,
                prompt_file=str(assignment),action_delay=5,
                progress_callback=lambda msg:record('progress',account=name,message=msg))
        except Exception as exc:
            (OUT/f'{name}_last_response.txt').write_text(await page.locator('body').inner_text(),encoding='utf-8')
            await page.screenshot(path=str(OUT/f'{name}_last_response.png'))
            record('failed',account=name,prompt=getattr(native,'last_prompt_number',0),error=str(exc))
            raise

async def main():
    prompts=re.findall(r'```(?:markdown)?\s*\n(.*?)```',SOURCE.read_text(encoding='utf-8-sig'),re.S)
    if len(prompts)!=10: raise RuntimeError(f'Expected 10 prompts, got {len(prompts)}')
    (OUT/'source_10_prompts.md').write_bytes(SOURCE.read_bytes())
    record('batch_start',source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),count=10)
    names=['FB_61595392250035','FB_61595209949134','FB_61595252550352',
           'FB_61594890465011','FB_61595197112743','FB_61595150824725',
           'FB_61595079638464','FB_61594878347315','FB_61594813873567','FB_61594860071693']
    previous=[]
    if (OUT/'manifest.jsonl').exists():
        previous=[json.loads(s) for s in (OUT/'manifest.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    # Never blindly repeat a request that may already be rendering. Explicit
    # rate refusals are retained for review instead of hammering the service.
    for group,name in enumerate(names):
        if any(r.get('event')=='failed' and r.get('account')==name and r.get('prompt',0)>0 for r in previous):
            continue
        numbered=list(enumerate(prompts[group*2:group*2+2],group*2+1))
        try:
            await run_pair(name,numbered)
        except Exception as exc:
            record('account_stopped',account=name,error=str(exc))
    record('batch_attempt_finished',downloaded=len(list(OUT.glob('*.mp4'))))

if __name__=='__main__': asyncio.run(main())
