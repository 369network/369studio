#!/usr/bin/env python3
"""369 Studio — Creator backend (v2, Supabase auth + multi-user wallet).

Wallet / ledger / characters live in Supabase (per-user, RLS + SECURITY DEFINER RPCs),
addressed with the CALLER'S JWT (no service-role key needed). Renders run the studio369
runners (Crun Seedance FAST t2v, Atlas GPT Image 2). Job tracking is local SQLite.

Env (defaults are the 369studio project; anon key is public-safe):
  SUPABASE_URL   default https://jjyguuctlqgvlbzifpuv.supabase.co
  SUPABASE_ANON  default <anon key>

Run:  cd studio369 && uvicorn server.app:app --host 0.0.0.0 --port 8080
"""
import os, sys, json, time, sqlite3, threading, subprocess, uuid, urllib.request, urllib.error
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV  = os.path.join(ROOT, "server"); JOBS = os.path.join(SRV, "jobs")
os.makedirs(JOBS, exist_ok=True)
# SECURITY/DURABILITY: the DB must live INSIDE the mounted disk (render.yaml mountPath=/app/server/jobs).
# It used to sit at server/jobs.db — on the ephemeral container filesystem — so every redeploy wiped
# job history while the renders it indexed survived. Migrate the old file once, then always use the disk.
DB = os.path.join(JOBS, "jobs.db")
_OLD_DB = os.path.join(SRV, "jobs.db")
if os.path.exists(_OLD_DB):
    try:
        if not os.path.exists(DB):
            import shutil; shutil.copy2(_OLD_DB, DB)
        # The old file holds JWTs written by an earlier build. Scrub them, then take it out of the
        # way so nothing reads or ships it again.
        _c = sqlite3.connect(_OLD_DB); _c.execute("UPDATE jobs SET token=NULL"); _c.commit(); _c.close()
        os.replace(_OLD_DB, _OLD_DB + ".migrated")
    except Exception: pass
SUPA_URL  = os.environ.get("SUPABASE_URL",  "https://jjyguuctlqgvlbzifpuv.supabase.co")
SUPA_ANON = os.environ.get("SUPABASE_ANON", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqeWd1dWN0bHFndmxiemlmcHV2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk2NDM4NTMsImV4cCI6MjEwNTIxOTg1M30.omSAlhkDfaZHALUnyXRD7Qdvu76-5kNKNv204MZ6LvM")

# ---- credit model (full model roster, SuperCool-parallel; all route to the Crun engine, price varies) ----
# NOTE: every video model currently renders on the same Crun Seedance FAST engine, so they
# are all priced at the Economy rate (1.0) — no premium is charged for output we don't deliver.
# `free` = 0 (gated to paid plans in generate()). When real Veo/Kling/etc. APIs are wired,
# raise these mults to match the delivered engine.
MODEL_MULT = {
  "frontier":1.0, "crun_fast":1.0, "free":0.0,
  "seedance25":1.0, "seedance2_mini":1.0, "seedance2_pro":1.0, "seedance2_fast":1.0,
  "veo31":1.0, "veo31_fast":1.0, "veo31_lite":1.0,
  "kling_o3_pro":1.0, "kling_o3_std":1.0,
  "pixverse":1.0, "ltx2_fast":1.0, "pvideo":1.0, "grok":1.0,
}
FREE_MODEL_DAILY_CAP = int(os.environ.get("FREE_MODEL_DAILY_CAP", "5"))  # free model = 0 credits but a REAL paid render
RES_MULT = {"360p":0.7,"480p":1.0,"720p":1.6,"1080p":2.4}
DUR_BASE = {"4s":128,"5s":160,"6s":192,"8s":256,"10s":320,"12s":384,"15s":480}
def credits_for(mode, model, res, dur):
    if mode=="image": return 5
    if mode=="music": return 60
    if mode in ("text","notes"): return 10
    return int(round(DUR_BASE.get(dur,480)*RES_MULT.get(res,1.0)*MODEL_MULT.get(model,1.0)))
def label_for(mode, model, res, dur): return f"Creator {mode} · {model} · {res} {dur}"

# ---- Supabase REST helpers (call as the user via their JWT) ----
def _req(method, path, token, body=None, params=""):
    url = f"{SUPA_URL}{path}{params}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("apikey", SUPA_ANON); r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read().decode(); return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, e.read().decode()[:200])
def auth_user(token):
    if not token: raise HTTPException(401, "sign in required")
    try:
        r = urllib.request.Request(f"{SUPA_URL}/auth/v1/user")
        r.add_header("apikey", SUPA_ANON); r.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        raise HTTPException(401, "invalid session")
def bearer(auth): return (auth or "").replace("Bearer ", "").strip()
def rpc(name, token, args): return _req("POST", f"/rest/v1/rpc/{name}", token, args)

# ---- local jobs db ----
def jdb():
    # WAL + busy_timeout: render threads write while API requests read. Default journal mode takes a
    # whole-DB write lock, which surfaced to users as a bogus "render failed".
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=30000")
    except Exception: pass
    return c
def initj():
    c = jdb(); c.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, uid TEXT, token TEXT, ts INT, status TEXT, credits INT, kind TEXT, label TEXT, file TEXT, err TEXT, qc TEXT, qc_note TEXT, transcript TEXT, retried INT DEFAULT 0)")
    for col,typ in (("qc","TEXT"),("qc_note","TEXT"),("transcript","TEXT"),("retried","INT DEFAULT 0"),
                    ("model","TEXT"),("refunded","INT DEFAULT 0")):
        try: c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
        except Exception: pass
    # SECURITY: we used to store the caller's Supabase JWT in this table forever. One file read
    # (or the old ref-traversal hole) was a session takeover for every user who had ever rendered.
    # Scrub any tokens written by an earlier build; new rows never store one.
    try: c.execute("UPDATE jobs SET token=NULL WHERE token IS NOT NULL")
    except Exception: pass
    c.commit(); c.close()
def setj(jid, **kw):
    c = jdb(); c.execute("UPDATE jobs SET "+",".join(f"{k}=?" for k in kw)+" WHERE id=?", list(kw.values())+[jid]); c.commit(); c.close()
initj()

def _reap_orphans():
    """Render work runs in daemon threads. Any restart — redeploy, OOM kill, failed health check —
    kills them, and the row stayed 'running' forever with the credits already deducted. On boot,
    anything still 'running' is by definition orphaned: fail it and return the credits."""
    try:
        c = jdb(); rows = c.execute("SELECT id FROM jobs WHERE status='running'").fetchall(); c.close()
        for r in rows:
            setj(r["id"], status="failed", err="interrupted by a restart; credits returned")
            _refund(r["id"])
        if rows: print(f"[reaper] released {len(rows)} orphaned job(s)", flush=True)
    except Exception as e:
        print(f"[reaper] {str(e)[:120]}", flush=True)

def _reap_stale(max_age=int(os.environ.get("JOB_MAX_AGE","3900"))):
    """A job still 'running' well past the runner's own timeout is not coming back."""
    while True:
        time.sleep(600)
        try:
            cut = int(time.time()) - max_age
            c = jdb(); rows = c.execute("SELECT id FROM jobs WHERE status='running' AND ts<?", (cut,)).fetchall(); c.close()
            for r in rows:
                setj(r["id"], status="failed", err="timed out; credits returned"); _refund(r["id"])
            if rows: print(f"[reaper] timed out {len(rows)} job(s)", flush=True)
        except Exception: pass

# ---- QC gate ----
# MEMORY: WhisperModel("small") is ~400-500 MB resident and was constructed FRESH on every video
# job, inside the web process, on a 512 MB box. Two concurrent renders was a guaranteed OOM kill,
# which restarted the container and orphaned every in-flight job. One cached instance, and an
# off switch for small instances (QC_WHISPER=0) — a worker process is still the real fix.
_WHISPER = None
_WHISPER_LOCK = threading.Lock()
def _whisper():
    global _WHISPER
    if os.environ.get("QC_WHISPER", "1") in ("0", "false", "off"): return None
    if _WHISPER is None:
        with _WHISPER_LOCK:
            if _WHISPER is None:
                from faster_whisper import WhisperModel
                _WHISPER = WhisperModel(os.environ.get("QC_WHISPER_MODEL", "tiny"), compute_type="int8")
    return _WHISPER

# Nothing capped in-flight renders: N users pressing Generate = N subprocesses + N ffmpeg runs.
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
_JOB_SLOTS = threading.Semaphore(MAX_CONCURRENT_JOBS)
def qc_image(path, ar):
    try:
        sz = os.path.getsize(path)
        return {"ok": sz>3000, "note": f"{sz//1024} KB", "transcript": ""}
    except Exception as e:
        return {"ok": False, "note": str(e)[:80], "transcript": ""}
def qc_video(path, dur):
    ok=True; note=[]; transcript=""
    try:
        d = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],capture_output=True,text=True,timeout=60).stdout.strip()
        secs=float(d or 0)
        note.append(f"{secs:.1f}s"); ok = secs >= max(2, dur*0.6)
        wav=path+".wav"; subprocess.run(["ffmpeg","-y","-loglevel","error","-i",path,"-ac","1","-ar","16000",wav],timeout=120)
        try:
            m=_whisper()
            if m is None: note.append("whisper off")
            else:
                seg,_=m.transcribe(wav,language=os.environ.get("QC_WHISPER_LANG","en"))
                transcript=" ".join(s.text.strip() for s in seg)[:400]
        except Exception: note.append("whisper n/a")
        try: os.remove(wav)
        except Exception: pass
    except Exception as e:
        ok=False; note.append(str(e)[:60])
    return {"ok": ok, "note": " · ".join(note), "transcript": transcript}

# ---- keys.env into env (for gen.py music lane) ----
def _load_keys_env():
    for p in (os.path.expanduser("~/.config/keys.env"), os.path.expanduser("~/.config/keys_glm.env")):
        if os.path.exists(p):
            for l in open(p):
                if "=" in l and not l.strip().startswith("#"):
                    k,v=l.strip().split("=",1); os.environ.setdefault(k, v.strip().strip('"'))
    # GLM (Zhipu) as the default text lane if a GLM key is present
    if os.environ.get("GLM_API_KEY") and not os.environ.get("TEXT_API_KEY"):
        os.environ.setdefault("TEXT_API_KEY", os.environ["GLM_API_KEY"])
        os.environ.setdefault("TEXT_API_BASE", "https://api.z.ai/api/paas/v4")
        os.environ.setdefault("TEXT_MODEL", "glm-4.5-flash")
_load_keys_env()

def _text_gen(prompt):
    """Text lane (author/notes). OpenAI-compatible endpoint (GLM/Zhipu by default)."""
    base=os.environ.get("TEXT_API_BASE"); key=os.environ.get("TEXT_API_KEY"); model=os.environ.get("TEXT_MODEL","glm-4.5-flash")
    if not (base and key): raise RuntimeError("text model not configured (set TEXT_API_KEY)")
    body={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":2000}
    req=urllib.request.Request(base.rstrip('/')+"/chat/completions",data=json.dumps(body).encode(),method="POST")
    req.add_header("Authorization",f"Bearer {key}"); req.add_header("Content-Type","application/json")
    with urllib.request.urlopen(req,timeout=180) as r:
        m=json.loads(r.read().decode())["choices"][0]["message"]
        return (m.get("content") or m.get("reasoning_content") or "").strip()

# ---- render worker ----
def _render_once(jdir, prompt, mode, res, dur, ar, refs, fields=None, audio=True):
    for sub in ("docs","renders","refs"): os.makedirs(os.path.join(jdir,sub),exist_ok=True)
    open(os.path.join(jdir,"docs","p.txt"),"w").write(prompt)
    fields = fields or {}
    if mode=="image":
        man=[{"id":"out","prompt":"docs/p.txt","size":"1024x1536" if ar in ("9:16","4:5") else ("1024x1024" if ar=="1:1" else "1536x1024")}]
        if refs: man[0]["refs"]=refs   # Atlas edit-with-refs (identity)
        json.dump(man,open(os.path.join(jdir,"gen.json"),"w"))
        subprocess.run([sys.executable,os.path.join(ROOT,"tools","run_atlas_img.py"),jdir,"gen.json"],cwd=ROOT,timeout=1500)
        return os.path.join(jdir,"refs","out.png")
    elif mode=="music":
        args=[sys.executable,os.path.join(ROOT,"tools","gen.py"),"music","--proj",jdir,"--item","out",
              "--style",fields.get("style","cinematic")[:120],"--title",fields.get("title","Untitled")[:60]]
        if fields.get("lyrics","").strip():
            lf=os.path.join(jdir,"docs","lyrics.txt"); open(lf,"w").write(fields["lyrics"]); args+=["--lyrics-file",lf]
        subprocess.run(args,cwd=ROOT,timeout=1500)
        return os.path.join(jdir,"renders","out.mp3")
    elif mode in ("text","notes"):
        txt=_text_gen(prompt); out=os.path.join(jdir,"renders","out.txt"); open(out,"w").write(txt); return out
    else:
        if refs:  # reference-to-video (character-sheet identity lock)
            man=[{"id":"out","mode":"B","dur":int(dur.replace("s","")),"prompt":"docs/p.txt","ar":ar,"res":res,"refs":refs,"audio":bool(audio)}]
        else:     # text-to-video
            man=[{"id":"out","mode":"T","dur":int(dur.replace("s","")),"prompt":"docs/p.txt","ar":ar,"res":res,"audio":bool(audio)}]
        json.dump(man,open(os.path.join(jdir,"gen.json"),"w"))
        subprocess.run([sys.executable,os.path.join(ROOT,"tools","run_crun.py"),jdir,"gen.json"],cwd=ROOT,timeout=3000)
        return os.path.join(jdir,"renders","cr_out.mp4")

def run_job(jid, prompt, mode, model, res, dur, ar, refs, template="", fields=None, uid=None, token=None, audio=True):
    jdir = os.path.join(JOBS, jid); fields = fields or {}
    with _JOB_SLOTS:
        _run_job_inner(jid, jdir, prompt, mode, model, res, dur, ar, refs, template, fields, uid, token, audio)

def _run_job_inner(jid, jdir, prompt, mode, model, res, dur, ar, refs, template, fields, uid, token, audio):
    try:
        out = _render_once(jdir, prompt, mode, res, dur, ar, refs, fields, audio)
        if not (os.path.exists(out) and os.path.getsize(out)>0):
            _refund(jid, token); setj(jid,status="failed",err="no output produced"); return
        # QC gate (technical)
        if mode=="image": q=qc_image(out,ar)
        elif mode=="video": q=qc_video(out,int(dur.replace("s","")))
        else: q={"ok":os.path.getsize(out)>10,"note":f"{os.path.getsize(out)}B","transcript":""}
        if not q["ok"] and mode in ("image","video"):
            c=jdb(); r=c.execute("SELECT retried FROM jobs WHERE id=?",(jid,)).fetchone(); c.close()
            if not (r and r["retried"]):
                setj(jid, retried=1, qc_note="retry: "+q["note"])
                out = _render_once(jdir+"_r", prompt, mode, res, dur, ar, refs, fields, audio)
                if os.path.exists(out) and os.path.getsize(out)>0:
                    q = qc_image(out, ar) if mode=="image" else qc_video(out, int(dur.replace("s","")))
        ext = ".png" if mode=="image" else (".mp3" if mode=="music" else (".txt" if mode in ("text","notes") else ".mp4"))
        # optional: push to R2/S3 and serve the CDN URL (no-op if unconfigured)
        try:
            from server.storage import put_output
            url = put_output(out, jid + ext)
            if url: out = url
        except Exception: pass
        setj(jid, status="done", file=out, qc=("pass" if q["ok"] else "warn"),
             qc_note=q.get("note",""), transcript=q.get("transcript",""))
        # save reusable character (sheets / influencer) so it appears in the r2v picker
        try:
            from server.templates import TEMPLATES
            if token and TEMPLATES.get(template,{}).get("save_character") or (template=="sheets"):
                nm = (fields or {}).get("name") or "Character"
                relpath = os.path.relpath(out, ROOT) if not str(out).startswith("http") else out
                imgurl = out if str(out).startswith("http") else f"/api/file/{jid}"
                _req("POST","/rest/v1/characters",token,body={"user_id":uid,"name":nm,"type":"Human","gender":"","meta":{"ref":relpath,"img":imgurl,"custom":True}})
        except Exception: pass
    except Exception as e:
        _refund(jid, token); setj(jid,status="failed",err=str(e)[:300])
def _refund(jid, token=None):
    """Return a failed job's credits.

    Two changes from the old version:
      - the JWT is no longer read from the DB (we don't store it); it is passed in from the worker.
      - if SUPABASE_SERVICE_KEY is set we refund with the service role instead. That matters because
        a user JWT expires in ~1 h while a video job can run 50 min + a QC retry, so the long
        expensive jobs were exactly the ones whose refund 401'd — silently, into `except: pass`,
        while the UI told the user "Credits refunded."
      - a refund that does not land is recorded, not swallowed.
    """
    c=jdb(); r=c.execute("SELECT uid,credits,label FROM jobs WHERE id=?", (jid,)).fetchone(); c.close()
    if not r: return
    item = "refund · "+(r["label"] or "")
    svc = os.environ.get("SUPABASE_SERVICE_KEY","")
    if svc:
        try:
            req = urllib.request.Request(f"{SUPA_URL}/rest/v1/rpc/add_credits",
                data=json.dumps({"p_user": r["uid"], "p_amount": r["credits"], "p_item": item}).encode(), method="POST")
            req.add_header("apikey", svc); req.add_header("Authorization", f"Bearer {svc}")
            req.add_header("Content-Type","application/json")
            with urllib.request.urlopen(req, timeout=20): pass
            setj(jid, refunded=1); return
        except Exception as e:
            print(f"[refund] service-role refund failed for {jid}: {str(e)[:120]}", flush=True)
    if token:
        try:
            rpc("refund_credits", token, {"p_amount": r["credits"], "p_item": item})
            setj(jid, refunded=1); return
        except Exception as e:
            print(f"[refund] user-token refund failed for {jid}: {str(e)[:120]}", flush=True)
    setj(jid, refunded=-1)   # -1 = owed, never returned. Reconcile these.
    print(f"[refund] UNREFUNDED {jid}: {r['credits']} credits owed to {r['uid']}", flush=True)

# ---- reference-path allow-list ----
# SECURITY: r.refs is raw client input and is handed to the runners, which curl -F @<path> the file
# to a PUBLIC host to give the model a fetchable URL. Before this guard, refs=["../../root/.config/
# keys_crun.env"] published our API keys. A ref is only ever one of two things:
#   1. something this user uploaded    -> server/jobs/_uploads/<uid>/<file>
#   2. an output of this user's own job -> server/jobs/<jid>/<file>, where jobs.uid == uid
# Anything else is rejected and dropped.
REF_EXTS = {".png",".jpg",".jpeg",".webp"}
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "12")) * (1 << 20)
def safe_refs(uid, paths):
    up_root = os.path.realpath(os.path.join(JOBS, "_uploads", uid))
    jobs_root = os.path.realpath(JOBS)
    ok = []
    for p in (paths or []):
        if not isinstance(p, str) or not p or p.startswith(("http://","https://")): continue
        full = os.path.realpath(os.path.join(ROOT, p))
        if not os.path.isfile(full): continue
        if os.path.splitext(full)[1].lower() not in REF_EXTS: continue
        if full == up_root or full.startswith(up_root + os.sep):
            ok.append(full); continue
        # a job output: server/jobs/<jid>/... and that job must belong to this user
        if full.startswith(jobs_root + os.sep):
            rel = os.path.relpath(full, jobs_root).split(os.sep)
            if len(rel) >= 2 and not rel[0].startswith("_"):
                try:
                    c = jdb(); row = c.execute("SELECT uid FROM jobs WHERE id=?", (rel[0],)).fetchone(); c.close()
                except Exception: row = None
                if row and row["uid"] == uid: ok.append(full); continue
        print(f"[safe_refs] rejected ref from uid={uid}: {p!r}", flush=True)
    return ok[:9]

# ---- API ----
app = FastAPI(title="369 Studio API v2")

@app.on_event("startup")
def _startup():
    _reap_orphans()
    threading.Thread(target=_reap_stale, daemon=True).start()
class CostReq(BaseModel):
    mode:str="video"; model:str="crun_fast"; res:str="480p"; dur:str="15s"
class GenReq(CostReq):
    prompt:str=""; ar:str="9:16"; audio:bool=True; refs:list=[]  # server-side ref paths (character sheets) for r2v/edit
    template:str=""; fields:dict={}  # app template id + its field values
class CharReq(BaseModel):
    name:str; type:str="Human"; gender:str="Female"; meta:dict={}

@app.get("/api/me")
def me(authorization: str = Header(None)):
    t = bearer(authorization); u = auth_user(t); uid = u["id"]
    prof = _req("GET","/rest/v1/profiles",t,params=f"?id=eq.{uid}&select=wallet,plan,display_name")
    led  = _req("GET","/rest/v1/ledger",t,params=f"?user_id=eq.{uid}&select=ts,item,credits,kind&order=ts.desc&limit=50")
    p = (prof or [{}])[0]
    return {"wallet": p.get("wallet",0), "plan": p.get("plan","free"), "name": p.get("display_name"), "ledger": led or []}

@app.post("/api/cost")
def cost(r: CostReq): return {"credits": credits_for(r.mode,r.model,r.res,r.dur)}

@app.get("/api/apps")
def apps():
    try:
        from server.templates import catalog; return catalog()
    except Exception: return []

@app.post("/api/generate")
def generate(r: GenReq, authorization: str = Header(None)):
    t = bearer(authorization); u = auth_user(t); uid = u["id"]
    # app template? -> shape prompt + params
    if r.template:
        try:
            from server.templates import apply_template
            ap = apply_template(r.template, r.prompt, r.fields)
            if ap:
                r.prompt=ap["prompt"]; r.mode=ap["mode"]; r.model=ap["model"]; r.res=ap["res"]; r.dur=ap["dur"]; r.ar=ap["ar"]
        except Exception: pass
    # Free Model is only for active paid plans (matches the UI promise)
    if r.model == "free":
        prof = _req("GET","/rest/v1/profiles",t,params=f"?id=eq.{uid}&select=plan")
        plan = ((prof or [{}])[0] or {}).get("plan","free")
        if str(plan).lower() in ("", "free", "none", None):
            raise HTTPException(402, "Free Model requires an active paid plan")
        # MONEY: the free model costs 0 credits but still submits a real, paid Crun job. Without a
        # ceiling any cheapest-tier account could render unlimited video at our expense. Cap it.
        since = int(time.time()) - 86400
        c=jdb(); used=c.execute("SELECT COUNT(*) FROM jobs WHERE uid=? AND model='free' AND ts>? AND status!='failed'",
                                (uid, since)).fetchone()[0]; c.close()
        if used >= FREE_MODEL_DAILY_CAP:
            raise HTTPException(429, f"Free Model limit reached ({FREE_MODEL_DAILY_CAP}/day). Pick another model or try tomorrow.")
    cr = credits_for(r.mode,r.model,r.res,r.dur)
    # hold credits now (atomic; raises if insufficient)
    try: rpc("spend_credits", t, {"p_amount":cr,"p_item":label_for(r.mode,r.model,r.res,r.dur),"p_kind":r.mode})
    except HTTPException as e:
        raise HTTPException(402, "Not enough credits")
    jid = uuid.uuid4().hex[:12]
    refs = safe_refs(uid, r.refs)
    # NOTE: the caller's JWT is deliberately NOT persisted (see _refund). It stays in memory,
    # passed to the worker thread only.
    c=jdb(); c.execute("INSERT INTO jobs(id,uid,token,ts,status,credits,kind,label,file,err,model) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (jid,uid,None,int(time.time()),"running",cr,r.mode,label_for(r.mode,r.model,r.res,r.dur),None,None,r.model)); c.commit(); c.close()
    threading.Thread(target=run_job,args=(jid,r.prompt,r.mode,r.model,r.res,r.dur,r.ar,refs,r.template,r.fields,uid,t,r.audio),daemon=True).start()
    return {"job_id":jid,"credits":cr}

@app.get("/api/job/{jid}")
def job(jid: str, authorization: str = Header(None)):
    u = auth_user(bearer(authorization))
    c=jdb(); r=c.execute("SELECT id,uid,status,credits,kind,label,file,err,qc,qc_note,transcript FROM jobs WHERE id=?", (jid,)).fetchone(); c.close()
    if not r or r["uid"]!=u["id"]: raise HTTPException(404,"no job")
    d=dict(r); d["file"]=f"/api/file/{jid}" if d["file"] else None; return d

@app.get("/api/file/{jid}")
def file(jid: str):
    from fastapi.responses import RedirectResponse
    c=jdb(); r=c.execute("SELECT file FROM jobs WHERE id=?", (jid,)).fetchone(); c.close()
    if not r or not r["file"]: raise HTTPException(404,"no file")
    f=r["file"]
    if f.startswith("http"): return RedirectResponse(f)           # R2/S3 CDN URL
    if not os.path.exists(f): raise HTTPException(404,"no file")
    return FileResponse(f)

UPLOADS = os.path.join(JOBS, "_uploads"); os.makedirs(UPLOADS, exist_ok=True)
@app.post("/api/upload")
async def upload(file: UploadFile = File(...), authorization: str = Header(None)):
    """Attach a reference image (for Reference→Video / Talking Head / AI Editor). Returns a server ref path."""
    u = auth_user(bearer(authorization)); uid = u["id"]
    d = os.path.join(UPLOADS, uid); os.makedirs(d, exist_ok=True)
    # SECURITY: the extension was taken from the client and served back by /api/upfile, so a
    # ".html" upload executed as script on our own origin — where the Supabase session lives.
    # Only image extensions are accepted now, and the file is re-typed from its magic bytes.
    ext = os.path.splitext(file.filename or "img.png")[1].lower()
    if ext not in REF_EXTS: raise HTTPException(400, "only .png/.jpg/.jpeg/.webp uploads are accepted")
    # MEMORY: this used to be `await file.read()` — the whole body into RAM with no cap, which is a
    # one-request kill on a 512 MB box. Stream it and stop at the limit.
    name = uuid.uuid4().hex[:10] + ext
    dst = os.path.join(d, name); total = 0
    with open(dst, "wb") as f:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk: break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                f.close(); os.remove(dst)
                raise HTTPException(413, f"file too large (max {MAX_UPLOAD_BYTES//(1<<20)} MB)")
            f.write(chunk)
    head = open(dst, "rb").read(12)
    if not (head[:8] == b"\x89PNG\r\n\x1a\n" or head[:3] == b"\xff\xd8\xff" or head[:4] == b"RIFF"):
        os.remove(dst); raise HTTPException(400, "not a valid PNG/JPEG/WEBP image")
    return {"ref": os.path.relpath(dst, ROOT), "url": f"/api/upfile/{uid}/{name}", "name": file.filename}
@app.get("/api/upfile/{uid}/{name}")
def upfile(uid: str, name: str):
    # SECURITY: `uid` came straight off the URL and was joined unchecked, so an encoded ../ walked
    # out of _uploads. Confine the resolved path to this user's folder and serve a fixed image type.
    base = os.path.realpath(os.path.join(UPLOADS, os.path.basename(uid)))
    p = os.path.realpath(os.path.join(base, os.path.basename(name)))
    if not p.startswith(base + os.sep) or not os.path.isfile(p): raise HTTPException(404, "no file")
    if os.path.splitext(p)[1].lower() not in REF_EXTS: raise HTTPException(404, "no file")
    return FileResponse(p, media_type="image/png" if p.endswith(".png") else "image/jpeg")

@app.get("/api/characters")
def chars(authorization: str = Header(None)):
    t=bearer(authorization); u=auth_user(t)
    return _req("GET","/rest/v1/characters",t,params=f"?user_id=eq.{u['id']}&select=id,name,type,gender,meta&order=created_at.desc") or []
@app.post("/api/characters")
def add_char(r: CharReq, authorization: str = Header(None)):
    t=bearer(authorization); u=auth_user(t)
    _req("POST","/rest/v1/characters",t,body={"user_id":u["id"],"name":r.name,"type":r.type,"gender":r.gender,"meta":r.meta})
    return {"ok":True}

# optional billing (active only when STRIPE_SECRET_KEY is set)
try:
    from server.stripe_billing import router as billing_router
    app.include_router(billing_router)
except Exception:
    pass

class AgentReq(BaseModel):
    message:str; persona:str=""
@app.post("/api/agent")
def agent(r: AgentReq, authorization: str = Header(None)):
    """Agent / AI-employee chat lane (text model) + light media-intent routing."""
    auth_user(bearer(authorization))  # must be signed in
    sysp = r.persona or ("You are 369 Studio's agent — a fast, friendly creative orchestrator. "
        "Help the user plan and make images, video, music, ads and copy. Be concise and practical.")
    reply=""
    try: reply=_text_gen(sysp+"\n\nUser: "+r.message+"\n\nReply concisely:")
    except Exception as e: reply="(text engine not configured yet — set TEXT_API_KEY. "+str(e)[:80]+")"
    action=None
    m=r.message.lower()
    if not r.persona:
        if any(k in m for k in ("video","clip","commercial","ad ","reel","film","movie","animation")):
            action={"label":"🎬 Make it in Creator","href":"/creator"}
        elif any(k in m for k in ("image","photo","picture","poster","logo","thumbnail")):
            action={"label":"🖼 Make it in Creator","href":"/creator"}
        elif any(k in m for k in ("song","music","track","beat","jingle")):
            action={"label":"🎵 Make it in Music Studio","href":"/app?app=music"}
    return {"reply":reply, "action":action}

# ---- page routes (SuperCool-parallel surfaces) ----
def _page(name): return open(os.path.join(SRV,"static",name),encoding="utf-8").read()
@app.get("/", response_class=HTMLResponse)
def home(): return _page("home.html")
@app.get("/creator", response_class=HTMLResponse)
def creator(): return _page("creator.html")
@app.get("/apps", response_class=HTMLResponse)
def appsgrid(): return _page("apps.html")
@app.get("/app", response_class=HTMLResponse)
def appspage(): return _page("app.html")
@app.get("/employees", response_class=HTMLResponse)
def employees(): return _page("employees.html")
@app.get("/agency", response_class=HTMLResponse)
def agency(): return _page("agency.html")
@app.get("/feed", response_class=HTMLResponse)
def feed(): return _page("feed.html")
@app.get("/watch", response_class=HTMLResponse)
def watch(): return _page("watch.html")
@app.get("/pricing", response_class=HTMLResponse)
def pricing(): return _page("pricing.html")
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(): return _page("dashboard.html")
@app.get("/library", response_class=HTMLResponse)
def library(): return _page("library.html")

# ---- voice-clone lane (ElevenLabs) ----
VOICES = os.path.join(JOBS, "_voices"); os.makedirs(VOICES, exist_ok=True)
VMAP = os.path.join(JOBS, "_voicemap.json")
DEFAULT_ELEVEN_VOICE = os.environ.get("VOICE_DEFAULT_ID", "21m00Tcm4TlvDq8ikWAM")  # public "Rachel"
def _vmap():
    try: return json.load(open(VMAP))
    except Exception: return {}
def _vmap_save(m):
    try: json.dump(m, open(VMAP,"w"))
    except Exception: pass
def _eleven_clone(key, sample_path, name):
    b = "----369"+uuid.uuid4().hex
    with open(sample_path,"rb") as f: audio=f.read()
    body  = (f'--{b}\r\nContent-Disposition: form-data; name="name"\r\n\r\n{name}\r\n').encode()
    body += (f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="s.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode()+audio+b"\r\n"
    body += (f'--{b}--\r\n').encode()
    req=urllib.request.Request("https://api.elevenlabs.io/v1/voices/add",data=body,method="POST")
    req.add_header("xi-api-key",key); req.add_header("Content-Type",f"multipart/form-data; boundary={b}")
    with urllib.request.urlopen(req,timeout=120) as resp:
        return json.loads(resp.read().decode())["voice_id"]
def _eleven_tts(key, voice_id, text, out):
    body={"text":text,"model_id":"eleven_multilingual_v2"}
    req=urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",data=json.dumps(body).encode(),method="POST")
    req.add_header("xi-api-key",key); req.add_header("Content-Type","application/json"); req.add_header("Accept","audio/mpeg")
    with urllib.request.urlopen(req,timeout=120) as resp: open(out,"wb").write(resp.read())
    return out

class VoiceReq(BaseModel):
    text:str; voice_id:str=""
@app.post("/api/voice")
def voice(r: VoiceReq, authorization: str = Header(None)):
    """Voice-clone lane. With VOICE_API_KEY (ElevenLabs), clones the character's 10s sample
    (cached) and speaks the text in that voice. Falls back to a default voice if cloning is
    unavailable on the plan. Costs 15 credits on success (refunded on failure)."""
    t = bearer(authorization); auth_user(t)
    key = os.environ.get("VOICE_API_KEY") or os.environ.get("ELEVEN_API_KEY")
    if not key:
        return {"file": None, "note": "Voice-clone is wired but off — add VOICE_API_KEY (ElevenLabs) in Render env to go live."}
    txt = (r.text or "").strip()[:800]
    if not txt: raise HTTPException(400, "empty text")
    # hold 15 credits
    try: rpc("spend_credits", t, {"p_amount":15,"p_item":"Voice · "+(r.voice_id or "tts"),"p_kind":"voice"})
    except HTTPException: raise HTTPException(402, "Not enough credits")
    try:
        vm = _vmap(); vid = r.voice_id or ""
        sample = os.path.join(SRV,"static","library", vid+".mp3")
        evid = None
        if vid and vid in vm: evid = vm[vid]
        elif vid and os.path.exists(sample):
            try: evid = _eleven_clone(key, sample, "369-"+vid); vm[vid]=evid; _vmap_save(vm)
            except Exception: evid = DEFAULT_ELEVEN_VOICE   # plan may not allow cloning
        else: evid = DEFAULT_ELEVEN_VOICE
        name = uuid.uuid4().hex[:10]+".mp3"; out = os.path.join(VOICES, name)
        _eleven_tts(key, evid, txt, out)
        cloned = (evid != DEFAULT_ELEVEN_VOICE)
        note = None
        if vid and not cloned:
            # server/static/library/ was empty, so every "clone" silently fell back to the stock
            # voice while still charging 15 credits. Say so.
            note = (f"no voice sample for '{vid}' in server/static/library — used the stock voice"
                    if not os.path.exists(sample) else
                    f"cloning unavailable on this plan — used the stock voice")
        return {"file": f"/api/voicefile/{name}", "cloned": cloned, "note": note}
    except Exception as e:
        try: rpc("refund_credits", t, {"p_amount":15,"p_item":"refund · voice"})
        except Exception: pass
        return {"file": None, "note": "Voice error: "+str(e)[:120]}
@app.get("/api/voicefile/{name}")
def voicefile(name: str):
    p = os.path.join(VOICES, os.path.basename(name))
    if not os.path.exists(p): raise HTTPException(404,"no file")
    return FileResponse(p)
@app.get("/config.js")
def cfg(): return HTMLResponse(f'window.SUPA_URL="{SUPA_URL}";window.SUPA_ANON="{SUPA_ANON}";', media_type="application/javascript")
app.mount("/static", StaticFiles(directory=os.path.join(SRV,"static")), name="static")
