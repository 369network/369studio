# usage: run_clips2.py <proj> <manifest.json> [ids] — mode A (first/last) or B (refs); items c2_<id>
import json,subprocess,sys,os,concurrent.futures as cf
proj,man=sys.argv[1],sys.argv[2]; only=set(sys.argv[3:]); M=json.load(open(f'projects/{proj}/{man}'))
def run(m):
    item='c2_'+m['id'].replace('-','_'); out=f'projects/{proj}/renders/{item}.mp4'
    if os.path.exists(out) and os.path.getsize(out)>0: return m['id'],'exists'
    cmd=['python3','tools/gen.py','video','--proj',proj,'--item',item,'--lane','protoface_h3','--prompt-file',f'projects/{proj}/{m["prompt"]}','--duration',str(m['dur']),'--ratio','9:16','--resolution','768p']
    if m.get('mode')=='A': cmd+=['--image',m['first'],'--end-image',m['last']]
    else: cmd+=['--refs',*m['refs']]
    r=subprocess.run(cmd,capture_output=True,text=True); open(f'projects/{proj}/renders/{item}.log','w').write(r.stdout+'\n'+r.stderr)
    return m['id'],('ok' if r.returncode==0 else 'FAIL '+r.stderr[-200:])
jobs=[m for m in M if not only or m['id'] in only]
with cf.ThreadPoolExecutor(2) as ex:
    for sid,st in ex.map(run,jobs): print(sid,st,flush=True)
