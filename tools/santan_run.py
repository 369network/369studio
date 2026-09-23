# Sequential chained runner: each scene gets its character sheets + previous clip's last frame.
import json,os,subprocess,sys
P="projects/santan"
SC=json.load(open(f"{P}/scenes_A.json"))
CHARREF={"suman":"refs/suman.png","aakash":"refs/aakash.png","naina":"refs/naina.png",
         "saas":"refs/saas.png","mausi":"refs/mausi.png","kamla":"refs/kamla.png",
         "suman_blue":"refs/suman.png","naina_bride":"refs/naina.png",
         "aakash_fest":"refs/aakash.png","saas_green":"refs/saas.png","mausi_wc":"refs/mausi.png"}
ids=sys.argv[1:]
env=dict(os.environ); env["CRUN_HOST"]="uguu"
for sid in ids:
    sc=SC[sid]
    out=f"{P}/renders/cr_s{sid}.mp4"
    if os.path.exists(out) and os.path.getsize(out)>100_000:
        print(f"skip s{sid} (exists)"); continue
    if os.path.exists(out): os.remove(out)
    refs=[CHARREF[c] for c in sc["chars"]]
    ch=sc["chain_from"]
    if ch:
        lf=f"renders/cr_s{ch}_last.png"
        if os.path.exists(f"{P}/{lf}"): refs.append(lf); print(f"s{sid} chained from s{ch}")
        else: print(f"s{sid} WARNING no last frame for s{ch} -> sheets only")
    man=[{"id":f"s{sid}","dur":10,"prompt":f"docs/s{sid}.txt","ar":"16:9","res":"480p","refs":refs,"audio":True}]
    mf=f"gen_s{sid}.json"; json.dump(man,open(f"{P}/{mf}","w"),ensure_ascii=False)
    r=subprocess.run(["python3","tools/run_crun.py",P,mf,f"s{sid}"],env=env,capture_output=True,text=True)
    tail="\n".join(r.stdout.strip().splitlines()[-3:])
    print(f"--- s{sid} ---\n{tail}")
    if not (os.path.exists(out) and os.path.getsize(out)>100_000):
        print(f"STOP: s{sid} failed"); break
