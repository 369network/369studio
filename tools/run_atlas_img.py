#!/usr/bin/env python3
"""Atlas Cloud GPT Image 2 runner (v7.5 image lane). PC or cloud (needs curl).
  python3 tools/run_atlas_img.py <proj_dir> <jobs.json> [ids...]
jobs.json items: {"id","prompt" (text or docs/x.txt), "refs":[local paths ≤N] (optional → edit model), "size":"1024x1024|1024x1536|1536x1024|2048x2048", "n":1}
  no refs -> openai/gpt-image-2/text-to-image ($0.004)   refs -> openai/gpt-image-2/edit ($0.005), refs hosted on litterbox (cached)
Outputs refs/<id>.png (+ renders/img_<id>.json). Resumable (renders/atlas_img_state.json).
Env: ATLAS_KEY or ~/.config/keys_atlas.env or <root>/.config/keys_atlas.env"""
import json,os,sys,subprocess,time
proj,man=sys.argv[1],sys.argv[2]; only=set(sys.argv[3:])
root=os.path.abspath(os.path.join(proj,'..','..'))
key=os.environ.get('ATLAS_KEY')
for kp in (os.path.expanduser('~/.config/keys_atlas.env'),os.path.join(root,'.config','keys_atlas.env')):
    if not key and os.path.exists(kp):
        for l in open(kp):
            if l.startswith('ATLAS_KEY='): key=l.strip().split('=',1)[1].strip('"')
if not key: sys.exit('ATLAS_KEY missing')
API='https://api.atlascloud.ai/api/v1/model'; H=['-H',f'Authorization: Bearer {key}','-H','Content-Type: application/json']
os.makedirs(f'{proj}/renders',exist_ok=True); os.makedirs(f'{proj}/refs',exist_ok=True)
sp=f'{proj}/renders/atlas_img_state.json'; up=f'{proj}/renders/crun_urls.json'
S=json.load(open(sp)) if os.path.exists(sp) else {}; U=json.load(open(up)) if os.path.exists(up) else {}
def curl(a):
    r=subprocess.run(['curl','-s','-m','180','-L']+a,capture_output=True,text=True)
    try: return json.loads(r.stdout)
    except Exception: return {'error':(r.stdout or r.stderr)[:300]}
def host(rel):
    p=os.path.join(proj,rel); k=f"{rel}:{int(os.path.getmtime(p))}"
    if k in U: return U[k]
    for attempt in range(4):
        r=subprocess.run(['curl','-s','-m','180','-F','reqtype=fileupload','-F','time=72h','-F',f'fileToUpload=@{p}','https://litterbox.catbox.moe/resources/internals/api.php'],capture_output=True,text=True).stdout.strip()
        if r.startswith('http'): break
        time.sleep(15*(attempt+1))
    if not r.startswith('http'): raise SystemExit(f'upload failed {rel}: {r[:120]}')
    U[k]=r; json.dump(U,open(up,'w'),indent=1); return r
M=[m for m in json.load(open(f'{proj}/{man}')) if not only or m['id'] in only]
for m in M:
    sid=m['id']; out=f"{proj}/refs/{sid}.png"
    if os.path.exists(out) and os.path.getsize(out)>0: continue
    if sid in S and S[sid].get('pid'): continue
    pr=m['prompt']; pr=open(f'{proj}/{pr}',encoding='utf-8').read() if pr.endswith('.txt') else pr
    body={'prompt':pr,'size':m.get('size','1024x1536'),'n':m.get('n',1)}
    if m.get('refs'): body['model']='openai/gpt-image-2/edit'; body['images']=[host(r) for r in m['refs']]
    else: body['model']='openai/gpt-image-2/text-to-image'
    j=curl(H+['-X','POST','-d',json.dumps(body,ensure_ascii=False),f'{API}/generateImage'])
    pid=(j.get('data') or {}).get('id'); S[sid]={'pid':pid,'submit':j}; json.dump(S,open(sp,'w'),indent=1)
    print('submit',sid,pid or j,flush=True)
pending={sid for sid in S if S[sid].get('pid') and not os.path.exists(f"{proj}/refs/{sid}.png")}
t0=time.time()
while pending and time.time()-t0<1200:
    for sid in sorted(pending):
        d=curl(H+[f"{API}/prediction/{S[sid]['pid']}"]).get('data') or {}; st=d.get('status')
        if st in ('completed','succeeded') and d.get('outputs'):
            out=f"{proj}/refs/{sid}.png"; subprocess.run(['curl','-s','-m','300','-L','-o',out,d['outputs'][0]]); json.dump(d,open(f'{proj}/renders/img_{sid}.json','w'),indent=1)
            print('done',sid,os.path.getsize(out),flush=True); pending.discard(sid)
        elif st in ('failed','timeout'):
            print('FAIL',sid,str(d.get('error'))[:200],flush=True); S[sid]['error']=d; json.dump(S,open(sp,'w'),indent=1); pending.discard(sid)
        else: print('poll',sid,st,flush=True)
    if pending: time.sleep(10)
print('remaining',sorted(pending))
