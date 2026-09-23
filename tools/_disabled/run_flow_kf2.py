"""Run keyframe jobs on flow-unlimited sequentially with paste-fail retry: python run_flow_kf2.py jobs.json [keys...]"""
import asyncio, json, os, sys, time
os.environ.setdefault("FLOW_DOTENV", r"C:\Users\admin\flow-unlimited-mcp\.env")
sys.path.insert(0, r"C:\Users\admin\flow-unlimited-mcp")
sys.stdout.reconfigure(encoding="utf-8")
from flow_unlimited_mcp import server as s
async def main():
    jobs=json.load(open(sys.argv[1],encoding='utf-8')); keys=sys.argv[2:]
    out=[]
    for j in jobs:
        if keys and j['key'] not in keys: continue
        t=time.time(); ok=False; r=''
        for attempt in range(3):
            try: r=await s.generate_image(**j['args'])
            except Exception as e: r=str(e)
            rs=str(r); ok=('"files"' in rs)
            if ok or 'no ingredient chip' not in rs: break
            await asyncio.sleep(5)
        rec={'key':j['key'],'ok':ok,'elapsed':round(time.time()-t),'result':r}
        out.append(rec); print(json.dumps({k:rec[k] for k in ['key','ok','elapsed']}), flush=True)
        json.dump(out,open('flow_kf_results.json','w',encoding='utf-8'),ensure_ascii=False,indent=1,default=str)
asyncio.run(main())
