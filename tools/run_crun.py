#!/usr/bin/env python3
"""Crun Seedance 2.0 FAST runner (v7.4 default video lane). Works on PC and cloud (needs curl).
  python3 tools/run_crun.py <proj_dir> <manifest.json> [ids...]
Manifest items (same as run_viggle): {"id","dur","prompt","refs":[...≤9],"mode","first","last","ar","res"}
  mode B/C: refs -> reference_images (identity: look portrait(s) + set + last frame)
  mode A : first(+last) -> bytedance/seedance2-0-fast-i2v img_urls (start frame) — refs are ignored in this mode
Refs are local files -> uploaded once to litterbox (72 h) and cached in renders/crun_urls.json.
Outputs renders/cr_<id>.mp4 (+ .json with credits); resumable (renders/crun_state.json).
Env: CRUN_KEY or ~/.config/keys_crun.env or <root>/.config/keys_crun.env. CRUN_RES (default 480p)."""
import json,os,sys,subprocess,time
proj,man=sys.argv[1],sys.argv[2]
_rest=sys.argv[3:]
# --retry/--force <ids>: a FAILED clip used to be unretryable forever, because the failure handler
# left its task_id in crun_state.json and the submit loop skips any id that already has one. The
# only recovery was hand-editing the state file. These flags clear that state first.
FORCE = '--force' in _rest or '--retry' in _rest
DRY   = '--dry-run' in _rest
only  = set(a for a in _rest if not a.startswith('-'))
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ledger.py')
PROJNAME = os.path.basename(os.path.normpath(proj))
def led(clip, **kw):
    """Best-effort ledger write. Never let bookkeeping break a render."""
    try:
        a=[sys.executable, LEDGER, 'record', PROJNAME, clip]
        for k,v in kw.items():
            if v is None: continue
            if v is True: a += ['--'+k.replace('_','-')]          # store_true flag
            else:         a += ['--'+k.replace('_','-'), str(v)]
        subprocess.run(a, capture_output=True, timeout=30)
    except Exception: pass
root=os.path.abspath(os.path.join(proj,'..','..'))
key=os.environ.get('CRUN_KEY')
for kp in (os.path.expanduser('~/.config/keys_crun.env'),os.path.join(root,'.config','keys_crun.env')):
    if not key and os.path.exists(kp):
        for l in open(kp):
            if l.startswith('CRUN_KEY='): key=l.strip().split('=',1)[1].strip('"')
if not key: sys.exit('CRUN_KEY missing')
MIN_OK=int(os.environ.get('CRUN_MIN_BYTES','400000'))  # smaller than this = truncated download
RES=os.environ.get('CRUN_RES','480p'); API='https://api.crun.ai/api/v1/client/job'
os.makedirs(f'{proj}/renders',exist_ok=True)
sp=f'{proj}/renders/crun_state.json'; up=f'{proj}/renders/crun_urls.json'
S=json.load(open(sp)) if os.path.exists(sp) else {}; U=json.load(open(up)) if os.path.exists(up) else {}
M=[m for m in json.load(open(f'{proj}/{man}')) if not only or m['id'] in only]
def curl(a):
    r=subprocess.run(['curl','-s','-m','180','-L']+a,capture_output=True,text=True)
    try: return json.loads(r.stdout)
    except Exception: return {'error':(r.stdout or r.stderr)[:300]}
HOSTPREF=os.environ.get('CRUN_HOST','litterbox').lower()  # set CRUN_HOST=uguu when ByteDance can't fetch litterbox
def _uguu(p):
    j=subprocess.run(['curl','-s','-m','180','-F',f'files[]=@{p}','https://uguu.se/upload'],capture_output=True,text=True).stdout
    try: return json.loads(j)['files'][0]['url']
    except Exception: return ''
def _litter(p):
    for attempt in range(2):
        r=subprocess.run(['curl','-s','-m','180','-F','reqtype=fileupload','-F','time=72h','-F',f'fileToUpload=@{p}','https://litterbox.catbox.moe/resources/internals/api.php'],capture_output=True,text=True).stdout.strip()
        if r.startswith('http'): return r
        time.sleep(5*(attempt+1))
    return ''
def host(rel):
    p=os.path.join(proj,rel); k=f"{rel}:{int(os.path.getmtime(p))}:{HOSTPREF}"
    if k in U: return U[k]
    order=[_uguu,_litter] if HOSTPREF=='uguu' else [_litter,_uguu]
    r=''
    for fn in order:
        r=fn(p)
        if r.startswith('http'): break
    if not r.startswith('http'): raise SystemExit(f'upload failed {rel}: {r[:120]}')
    U[k]=r; json.dump(U,open(up,'w'),indent=1); return r
# SECURITY: the key used to be passed as `-H "x-api-key: ..."` in argv, readable by any local
# process via `ps` / /proc/<pid>/cmdline for the life of the call. curl -K reads it from a
# 0600 file instead, so it never appears on a command line.
import tempfile, atexit
_kfd, _kcfg = tempfile.mkstemp(prefix='.crun-', suffix='.conf'); os.close(_kfd)
os.chmod(_kcfg, 0o600)
with open(_kcfg, 'w') as _f:
    _f.write(f'header = "x-api-key: {key}"\nheader = "Content-Type: application/json"\n')
atexit.register(lambda: os.path.exists(_kcfg) and os.remove(_kcfg))
H=['-K', _kcfg]
if FORCE:
    for sid in (only or set(S.keys())):
        if sid in S:
            print('force: clearing state for',sid,flush=True); S.pop(sid,None)
    json.dump(S,open(sp,'w'),indent=1)
if DRY:
    for m in M:
        pf=f"{proj}/{m['prompt']}"
        print(f"{m['id']:10} dur={m.get('dur')} ar={m.get('ar','9:16')} refs={len(m.get('refs',[]))} "
              f"prompt={'OK' if os.path.exists(pf) else 'MISSING'} "
              f"missing_refs={[r for r in m.get('refs',[]) if not os.path.exists(os.path.join(proj,r))]}")
    sys.exit(0)
for m in M:
    sid=m['id']; out=f"{proj}/renders/cr_{sid.replace('-','_')}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>MIN_OK: continue
    if sid in S and S[sid].get('tid'): continue
    prompt=open(f"{proj}/{m['prompt']}",encoding='utf-8').read()
    dur=max(4,min(15,int(m['dur']))); ar=m.get('ar','9:16'); res=m.get('res',RES)
    RLF=m.get('return_last_frame',True)  # always ask Crun for the last frame (continuity) unless explicitly off
    if m.get('mode')=='A':
        imgs=[host(m['first'])]+([host(m['last'])] if m.get('last') else [])
        body={'model':'bytedance/seedance2-0-fast-i2v','input':{'prompt':prompt,'img_urls':imgs,'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True),'return_last_frame':RLF}}
    elif m.get('mode')=='T':  # text-to-video (no refs) — 369 Studio Creator lane
        body={'model':'bytedance/seedance2-0-fast-t2v','input':{'prompt':prompt,'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True),'return_last_frame':RLF}}
    else:
        body={'model':'bytedance/seedance2-0-fast-r2v','input':{'prompt':prompt,'reference_images':[host(r) for r in m['refs'][:9]],'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True),'return_last_frame':RLF}}
    j=curl(H+['-X','POST','-d',json.dumps(body,ensure_ascii=False),f'{API}/CreateTask'])
    tid=(j.get('data') or {}).get('task_id'); S[sid]={'tid':tid,'submit':j}; json.dump(S,open(sp,'w'),indent=1)
    led(sid, task_id=tid, status='submitted', mode={'A':'i2v','T':'t2v'}.get(m.get('mode'),'r2v'),
        res=res, ar=ar, dur=dur, prompt_file=m['prompt'],
        refs=json.dumps(m.get('refs') or []), new_attempt=True if FORCE else None)
    print('submit',sid,tid or j,flush=True); time.sleep(1)
pending={sid for sid in S if (not only or sid in only) and S[sid].get('tid') and not (os.path.exists(f"{proj}/renders/cr_{sid.replace('-','_')}.mp4") and os.path.getsize(f"{proj}/renders/cr_{sid.replace('-','_')}.mp4")>MIN_OK)}
t0=time.time()
while pending and time.time()-t0<3600:
    for sid in sorted(pending):
        d=curl(H+[f"{API}/TaskInfo?task_id={S[sid]['tid']}"]).get('data') or {}; st=d.get('status')
        if st=='success':
            out=f"{proj}/renders/cr_{sid.replace('-','_')}.mp4"
            mu0=((d.get('result') or {}).get('media_urls') or [None])[0]
            json.dump(d,open(out+'.json','w'),indent=1)   # sidecar first: the URL is the receipt even if the download fails
            if not mu0:
                print('FAIL',sid,'success status but no media_urls',flush=True)
                led(sid,status='failed',error='success with no media_urls'); pending.discard(sid); continue
            # The CDN intermittently stalls; a partial file used to be recorded as a finished clip.
            ok=False
            for attempt in range(3):
                r=subprocess.run(['curl','-s','-m','300','-L','-o',out,mu0])
                if r.returncode==0 and os.path.exists(out) and os.path.getsize(out)>MIN_OK: ok=True; break
                print(f'retry download {sid} ({attempt+1}/3) rc={r.returncode} '
                      f'size={os.path.getsize(out) if os.path.exists(out) else 0}',flush=True); time.sleep(5)
            # save last frame Crun returned (return_last_frame) -> cr_<id>_last.png for next-clip continuity.
            # Crun appends the last frame as an extra image entry in media_urls (e.g. ..._1.png).
            res_d=d.get('result') or {}; mu=res_d.get('media_urls') or []; lf=None
            for u in mu[1:]:
                if isinstance(u,str) and u.lower().split('?')[0].endswith(('.png','.jpg','.jpeg','.webp')): lf=u; break
            if not lf:  # fallback: any last-frame-named field
                for k,v in res_d.items():
                    if 'last' in k.lower() and 'frame' in k.lower():
                        lf=v[0] if isinstance(v,list) and v else v; break
            if lf and str(lf).startswith('http'):
                lfp=f"{proj}/renders/cr_{sid.replace('-','_')}_last.png"
                subprocess.run(['curl','-s','-m','120','-L','-o',lfp,lf]); print('lastframe',sid,os.path.getsize(lfp) if os.path.exists(lfp) else 0,flush=True)
            cr=d.get('credits'); cr=cr if isinstance(cr,(int,float)) else None
            lfp_rel=f"projects/{PROJNAME}/renders/cr_{sid.replace('-','_')}_last.png"
            led(sid, status='success' if ok else 'truncated', media_url=mu0, last_frame_url=lf if lf else None,
                local_path=f"projects/{PROJNAME}/renders/cr_{sid.replace('-','_')}.mp4",
                last_frame_path=lfp_rel if os.path.exists(f"{proj}/renders/cr_{sid.replace('-','_')}_last.png") else None,
                credits=cr, error=None if ok else 'download truncated after 3 attempts')
            print(('done' if ok else 'TRUNCATED'),sid,os.path.getsize(out) if os.path.exists(out) else 0,
                  d.get('credits'),'cr',flush=True); pending.discard(sid)
        elif st=='failed':
            print('FAIL',sid,d,flush=True); S[sid]['error']=d; json.dump(S,open(sp,'w'),indent=1)
            led(sid,status='failed',error=json.dumps(d)[:280]); pending.discard(sid)
        else: print('poll',sid,st,flush=True)
    if pending: time.sleep(30)
print('remaining',sorted(pending))
if pending:
    print('  retry with:  python3 tools/run_crun.py',proj,man,'--retry',' '.join(sorted(pending)),flush=True)
