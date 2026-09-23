import json,subprocess,sys,os,concurrent.futures as cf
# usage: run_clips.py <proj> [ids...] — manifest projects/<proj>/docs/shots.json
proj=sys.argv[1]; sys.argv=sys.argv[:1]+sys.argv[2:]; M=json.load(open(f'projects/{proj}/docs/shots.json'))
only=set(sys.argv[1:])
def run(m):
    item='c_'+m['id'].replace('-','_')
    out=f'projects/{proj}/renders/{item}.mp4'
    if os.path.exists(out) and os.path.getsize(out)>0: return m['id'],'exists'
    cmd=['python3','tools/gen.py','video','--proj',proj,'--item',item,'--lane','protoface_h3','--prompt-file',f'projects/{proj}/{m["prompt"]}','--duration',str(m['dur']),'--ratio','9:16','--resolution','768p','--refs',*m['refs']]
    r=subprocess.run(cmd,capture_output=True,text=True)
    open(f'projects/{proj}/renders/{item}.log','w').write(r.stdout+'\n'+r.stderr)
    return m['id'],('ok' if r.returncode==0 else 'FAIL '+r.stderr[-300:])
jobs=[m for m in M if not only or m['id'] in only]
with cf.ThreadPoolExecutor(2) as ex:
    for sid,st in ex.map(run,jobs): print(sid,st,flush=True)
