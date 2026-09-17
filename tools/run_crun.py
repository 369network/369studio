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
proj,man=sys.argv[1],sys.argv[2]; only=set(sys.argv[3:])
root=os.path.abspath(os.path.join(proj,'..','..'))
key=os.environ.get('CRUN_KEY')
for kp in (os.path.expanduser('~/.config/keys_crun.env'),os.path.join(root,'.config','keys_crun.env')):
    if not key and os.path.exists(kp):
        for l in open(kp):
            if l.startswith('CRUN_KEY='): key=l.strip().split('=',1)[1].strip('"')
if not key: sys.exit('CRUN_KEY missing')
RES=os.environ.get('CRUN_RES','480p'); API='https://api.crun.ai/api/v1/client/job'
os.makedirs(f'{proj}/renders',exist_ok=True)
sp=f'{proj}/renders/crun_state.json'; up=f'{proj}/renders/crun_urls.json'
S=json.load(open(sp)) if os.path.exists(sp) else {}; U=json.load(open(up)) if os.path.exists(up) else {}
M=[m for m in json.load(open(f'{proj}/{man}')) if not only or m['id'] in only]
def curl(a):
    r=subprocess.run(['curl','-s','-m','180','-L']+a,capture_output=True,text=True)
    try: return json.loads(r.stdout)
    except Exception: return {'error':(r.stdout or r.stderr)[:300]}
def host(rel):
    p=os.path.join(proj,rel); k=f"{rel}:{int(os.path.getmtime(p))}"
    if k in U: return U[k]
    for attempt in range(2):
        r=subprocess.run(['curl','-s','-m','180','-F','reqtype=fileupload','-F','time=72h','-F',f'fileToUpload=@{p}','https://litterbox.catbox.moe/resources/internals/api.php'],capture_output=True,text=True).stdout.strip()
        if r.startswith('http'): break
        time.sleep(5*(attempt+1))
    if not r.startswith('http'):  # fallback: uguu.se (3 h, direct link)
        j=subprocess.run(['curl','-s','-m','180','-F',f'files[]=@{p}','https://uguu.se/upload'],capture_output=True,text=True).stdout
        try: r=json.loads(j)['files'][0]['url']; k=k+':uguu'
        except Exception: raise SystemExit(f'upload failed {rel}: {r[:120]}')
    U[k]=r; json.dump(U,open(up,'w'),indent=1); return r
H=['-H',f'x-api-key: {key}','-H','Content-Type: application/json']
for m in M:
    sid=m['id']; out=f"{proj}/renders/cr_{sid.replace('-','_')}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>0: continue
    if sid in S and S[sid].get('tid'): continue
    prompt=open(f"{proj}/{m['prompt']}",encoding='utf-8').read()
    dur=max(4,min(15,int(m['dur']))); ar=m.get('ar','9:16'); res=m.get('res',RES)
    if m.get('mode')=='A':
        imgs=[host(m['first'])]+([host(m['last'])] if m.get('last') else [])
        body={'model':'bytedance/seedance2-0-fast-i2v','input':{'prompt':prompt,'img_urls':imgs,'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True)}}
    elif m.get('mode')=='T':  # text-to-video (no refs) — 369 Studio Creator lane
        body={'model':'bytedance/seedance2-0-fast-t2v','input':{'prompt':prompt,'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True)}}
    else:
        body={'model':'bytedance/seedance2-0-fast-r2v','input':{'prompt':prompt,'reference_images':[host(r) for r in m['refs'][:9]],'resolution':res,'aspect_ratio':ar,'duration':dur,'audio':m.get('audio',True)}}
    j=curl(H+['-X','POST','-d',json.dumps(body,ensure_ascii=False),f'{API}/CreateTask'])
    tid=(j.get('data') or {}).get('task_id'); S[sid]={'tid':tid,'submit':j}; json.dump(S,open(sp,'w'),indent=1)
    print('submit',sid,tid or j,flush=True); time.sleep(1)
pending={sid for sid in S if S[sid].get('tid') and not os.path.exists(f"{proj}/renders/cr_{sid.replace('-','_')}.mp4")}
t0=time.time()
while pending and time.time()-t0<3600:
    for sid in sorted(pending):
        d=curl(H+[f"{API}/TaskInfo?task_id={S[sid]['tid']}"]).get('data') or {}; st=d.get('status')
        if st=='success':
            out=f"{proj}/renders/cr_{sid.replace('-','_')}.mp4"
            subprocess.run(['curl','-s','-m','300','-L','-o',out,d['result']['media_urls'][0]]); json.dump(d,open(out+'.json','w'),indent=1)
            print('done',sid,os.path.getsize(out),d.get('credits'),'cr',flush=True); pending.discard(sid)
        elif st=='failed':
            print('FAIL',sid,d,flush=True); S[sid]['error']=d; json.dump(S,open(sp,'w'),indent=1); pending.discard(sid)
        else: print('poll',sid,st,flush=True)
    if pending: time.sleep(30)
print('remaining',sorted(pending))
