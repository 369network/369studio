#!/usr/bin/env python3
"""PC-side viggle H3 runner (apis.viggle.ai). Usage:
  python3 run_viggle.py <proj_dir> <manifest.json> [ids...]   # submit all (or given ids), then poll+download
Manifest items: {"id","dur","prompt","refs":[...],"mode":"A"|"B","first","last"}  (same as run_clips2)
Outputs renders/vg_<id>.mp4 + renders/vg_<id>.json ; resumable (state in renders/viggle_state.json).
Env: VIGGLE_API_KEY (or .config/keys_viggle.env next to studio369 root). quality via VIGGLE_QUALITY (default high)."""
import json,os,sys,subprocess,time
proj,man=sys.argv[1],sys.argv[2]; only=set(sys.argv[3:])
root=os.path.abspath(os.path.join(proj,'..','..'))
key=os.environ.get('VIGGLE_API_KEY')
if not key:
    for l in open(os.path.join(root,'.config','keys_viggle.env')):
        if l.startswith('VIGGLE_API_KEY='): key=l.strip().split('=',1)[1].strip('"')
Q=os.environ.get('VIGGLE_QUALITY','high').strip(); API='https://apis.viggle.ai/v1/videos'
os.makedirs(f'{proj}/renders',exist_ok=True); sp=f'{proj}/renders/viggle_state_{Q}.json'
S=json.load(open(sp)) if os.path.exists(sp) else {}
M=[m for m in json.load(open(f'{proj}/{man}')) if not only or m['id'] in only]
def curl(args):
    r=subprocess.run(['curl','-s','-m','120','-L','-H',f'Authorization: Bearer {key}']+args,capture_output=True,text=True)
    try: return json.loads(r.stdout)
    except Exception: return {'error':r.stdout[:300] or r.stderr[:300]}
for m in M:
    sid=m['id']; out=f"{proj}/renders/vg{Q}_{sid.replace('-','_')}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>0: continue
    if sid in S and S[sid].get('vid'): continue
    dur=m['dur'] if m.get('mode')=='A' else max(5,m['dur'])  # viggle: reference mode fails instantly below 5 s
    lane=m.get('lane','')
    if lane.startswith('protoface'): continue
    res='1080p' if '1080' in lane else '768p'; ar=m.get('ar','9:16')
    args=['-F',f"prompt=<{proj}/{m['prompt']}",'-F',f'quality={Q}','-F',f"duration_s={dur}",'-F',f'resolution={res}','-F',f'aspect_ratio={ar}']
    if m.get('mode')=='A':
        args+=['-F',f"first_frame_image=@{proj}/{m['first']}"]
        if m.get('last'): args+=['-F',f"last_frame_image=@{proj}/{m['last']}"]
    else:
        for r in m['refs'][:4]: args+=['-F',f"reference_image=@{proj}/{r}"]
    j=curl(args+[API]); S[sid]={'vid':j.get('id'),'submit':j}; json.dump(S,open(sp,'w'),indent=1)
    print('submit',sid,j.get('id') or j,flush=True); time.sleep(2)
# poll
pending={sid for sid in S if S[sid].get('vid') and not os.path.exists(f"{proj}/renders/vg{Q}_{sid.replace('-','_')}.mp4")}
t0=time.time()
while pending and time.time()-t0<1800:
    for sid in sorted(pending):
        j=curl([f"{API}/{S[sid]['vid']}"]); st=j.get('status')
        if st=='ready' and j.get('video_url'):
            out=f"{proj}/renders/vg{Q}_{sid.replace('-','_')}.mp4"
            subprocess.run(['curl','-s','-m','120','-L','-o',out,j['video_url']]); json.dump(j,open(out+'.json','w'),indent=1)
            print('done',sid,os.path.getsize(out),flush=True); pending.discard(sid)
        else: print('poll',sid,st,j.get('progress'),flush=True)
        if st in ('failed','error'):
            print('FAIL',sid,j,flush=True); S[sid]['error']=j; json.dump(S,open(sp,'w'),indent=1); pending.discard(sid)
    if pending: time.sleep(20)
print('remaining',sorted(pending))
