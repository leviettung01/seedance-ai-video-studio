"""Slow, resumable Pro Skill batch through the tool's own temporary Chrome workers."""
import asyncio, hashlib, json, re, time
from pathlib import Path
from account_manager import AccountManager
from session_store import SessionStore
from proxy_manager import ProxyManager
from pro_skill_batch import ProSkillBatch
from create_pet_prompts20 import render, THEMES

SOURCE=Path(r'D:\SKILL VIDEO\Timelapse Phòng thú cưng\10_prompt_timelapse_thi_cong_phong_thu_cung_vip.md')
OUT=Path(r'D:\Seedance\output_videos\pet_room_batch30_20261022')
OUT.mkdir(parents=True,exist_ok=True)
MANIFEST=OUT/'manifest.jsonl'

def record(event,**fields):
    row={'time':time.time(),'event':event,**fields}
    with MANIFEST.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row,ensure_ascii=True),flush=True)

def rows():
    return [json.loads(x) for x in MANIFEST.read_text(encoding='utf-8').splitlines() if x.strip()] if MANIFEST.exists() else []

async def wait_rotation(previous):
    import httpx
    record('waiting_for_scheduled_fr_rotation')
    async with httpx.AsyncClient(trust_env=False,timeout=8) as c:
        for tick in range(24):
            await asyncio.sleep(15)
            try:
                state=(await c.get('http://127.0.0.1:9090/api/rotation/status')).json()
                row=next((p for p in state.get('ports',[]) if p.get('port')==10000),{})
                if row.get('last_ip') and row['last_ip']!=previous:
                    record('fr_exit_rotated',interval_seconds=state.get('interval_seconds'))
                    return True
            except Exception: pass
            if tick%4==3: record('rotation_pending')
    return False

async def main():
    source=SOURCE.read_bytes()
    prompts=re.findall(r'```(?:markdown)?\s*\n(.*?)```',source.decode('utf-8-sig'),re.S)
    if len(prompts)!=10: raise RuntimeError(f'Expected 10 numbered prompts; found {len(prompts)}')
    (OUT/'source_10_prompts.md').write_bytes(source)
    prompt20=OUT/'20_prompt_pet_room_timeline_11_30.txt'
    # If all original ten complete, author the second list from the same visual
    # rules and run it as PROMPT 11–30 in twenty separately numbered briefs.
    (OUT/'20_prompt_pet_room_timeline_11_30.txt').write_text(
        '\n\n'+'\n\n'+'\n\n'.join(render(i,t) for i,t in enumerate(THEMES,11)),encoding='utf-8')
    extra=[render(i,t) for i,t in enumerate(THEMES,11)]
    prior=rows();downloaded={r['prompt'] for r in prior if r.get('event')=='downloaded'}
    attempted_accounts={r['account'] for r in prior if r.get('event') in ('failed','account_stopped') and r.get('prompt',0)>0 and ('710022002' in r.get('error','') or 'AUTH_EXPIRED' in r.get('error',''))}
    accounts=AccountManager().get_all();store=SessionStore()
    available=[x['name'] for x in accounts if store.has_session(x['name']) and x['name'] not in attempted_accounts]
    preferred=['FB_61595392250035','FB_61595209949134','FB_61595252550352','FB_61594890465011','FB_61595197112743','FB_61595150824725','FB_61595079638464','FB_61594878347315','FB_61594813873567','FB_61594860071693']
    names=[x for x in preferred if x in available]+[x for x in available if x not in preferred]
    names=names[:10]
    if not names: raise RuntimeError('No unused saved Dola session is available.')
    record('batch_start',source_sha256=hashlib.sha256(source).hexdigest(),accounts_available=len(names),output=str(OUT))
    proxy=ProxyManager()
    # Use one account per pair. Failed or unfinished prompt numbers return to
    # the queue and are assigned to a fresh account after the hub rotates.
    queue=[(i+1,p) for i,p in enumerate(prompts) if i+1 not in downloaded]
    used=set(attempted_accounts); index=0; worker_id=0
    while queue and index<len(names):
        account=names[index];index+=1;used.add(account)
        pair=queue[:2]
        before_ip=''
        try:
            import httpx
            async with httpx.AsyncClient(trust_env=False,timeout=8) as c:
                state=(await c.get('http://127.0.0.1:9090/api/rotation/status')).json()
                before_ip=next((p.get('last_ip','') for p in state.get('ports',[]) if p.get('port')==10000),'')
        except Exception: pass
        assigned=OUT/f'{account}_prompts_{pair[0][0]:02d}_{pair[-1][0]:02d}.txt'
        assigned.write_text('\n\n'.join(f'PROMPT {n:02d}\n{text}' for n,text in pair),encoding='utf-8')
        record('assigned',account=account,prompts=[n for n,_ in pair],file=str(assigned))
        runner=ProSkillBatch()
        def progress(msg): record('progress',account=account,message=msg)
        def on_video(info): record('downloaded',account=account,prompt=info['prompt_number'],path=info['path'],duration=info['duration'],via='extension')
        try:
            await runner.run(account,[p for _,p in pair],'',len(pair),'9:16','',duration=30,
                show_browser=True,progress=progress,on_video=on_video,output_dir=OUT,manifest_path=MANIFEST)
            queue=queue[2:]
            await asyncio.sleep(12)
        except Exception as e:
            done=set(runner.completed_prompt_numbers)
            queue=[item for item in queue if item[0] not in done]
            failed=runner.last_failed_prompt
            record('account_stopped',account=account,prompt=failed,error=str(e))
            if '710022002' in str(e):
                if not await wait_rotation(before_ip):
                    record('batch_paused',reason='The scheduled French VPN2Proxy exit did not change.')
                    break
            await asyncio.sleep(20)
    if queue:
        record('first_10_incomplete',remaining=[n for n,_ in queue],accounts_used=index)
        return
    final={r['prompt'] for r in rows() if r.get('event')=='downloaded' and 1<=r.get('prompt',0)<=10}
    if len(final)<10:
        record('first_10_incomplete',remaining=sorted(set(range(1,11))-final));return
    record('first_10_complete')
    # The 20 new prompts are persisted before being sent.
    for group in range(0,20,2):
        account=names[(group//2)%len(names)]
        pair=list(enumerate(extra[group:group+2],11+group))
        assigned=OUT/f'{account}_prompts_{pair[0][0]:02d}_{pair[-1][0]:02d}.txt'
        assigned.write_text('\n\n'.join(f'PROMPT {n:02d}\n{txt}' for n,txt in pair),encoding='utf-8')
        record('assigned_new_prompt',account=account,prompts=[n for n,_ in pair],file=str(assigned))
        runner=ProSkillBatch()
        try:
            await runner.run(account,[p for _,p in pair],'',len(pair),'9:16','',duration=30,
                show_browser=True,progress=lambda m:record('progress',account=account,message=m),
                on_video=lambda v:record('downloaded',account=account,prompt=v['prompt_number'],path=v['path'],duration=v['duration'],via='extension'),
                output_dir=OUT,manifest_path=MANIFEST)
            await asyncio.sleep(12)
        except Exception as e:
            record('new_prompt_account_stopped',account=account,prompt=runner.last_failed_prompt,error=str(e))
            break
    record('batch_end',downloaded=len([r for r in rows() if r.get('event')=='downloaded']))

if __name__=='__main__': asyncio.run(main())
