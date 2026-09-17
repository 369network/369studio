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
SRV  = os.path.join(ROOT, "server"); JOBS = os.path.join(SRV, "jobs"); DB = os.path.join(SRV, "jobs.db")
os.makedirs(JOBS, exist_ok=True)
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
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def initj():
    c = jdb(); c.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, uid TEXT, token TEXT, ts INT, status TEXT, credits INT, kind TEXT, label TEXT, file TEXT, err TEXT, qc TEXT, qc_note TEXT, transcript TEXT, retried INT DEFAULT 0)")
    for col,typ in (("qc","TEXT"),("qc_note","TEXT"),("transcript","TEXT"),("retried","INT DEFAULT 0")):
        try: c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
        except Exception: pass
    c.commit(); c.close()
def setj(jid, **kw):
    c = jdb(); c.execute("UPDATE jobs SET "+",".join(f"{k}=?" for k in kw)+" WHERE id=?", list(kw.values())+[jid]); c.commit(); c.close()
initj()

# ---- QC gate ----
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
            from faster_whisper import WhisperModel
            m=WhisperModel("small",compute_type="int8"); seg,_=m.transcribe(wav,language="en")
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
    try:
        out = _render_once(jdir, prompt, mode, res, dur, ar, refs, fields, audio)
        if not (os.path.exists(out) and os.path.getsize(out)>0):
            _refund(jid); setj(jid,status="failed",err="no output produced"); return
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
                _req("POST","/rest/v1/characters",token,body={"user_id":uid,"name":nm,"type":"Human","gender":"","meta":{"ref":relpath}})
        except Exception: pass
    except Exception as e:
        _refund(jid); setj(jid,status="failed",err=str(e)[:300])
def _refund(jid):
    c=jdb(); r=c.execute("SELECT token,credits,label FROM jobs WHERE id=?", (jid,)).fetchone(); c.close()
    if r:
        try: rpc("refund_credits", r["token"], {"p_amount": r["credits"], "p_item": "refund · "+(r["label"] or "")})
        except Exception: pass

# ---- API ----
app = FastAPI(title="369 Studio API v2")
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
    cr = credits_for(r.mode,r.model,r.res,r.dur)
    # hold credits now (atomic; raises if insufficient)
    try: rpc("spend_credits", t, {"p_amount":cr,"p_item":label_for(r.mode,r.model,r.res,r.dur),"p_kind":r.mode})
    except HTTPException as e:
        raise HTTPException(402, "Not enough credits")
    jid = uuid.uuid4().hex[:12]
    refs = [p for p in (r.refs or []) if isinstance(p,str) and os.path.exists(os.path.join(ROOT,p))]
    refs = [os.path.join(ROOT,p) for p in refs]
    c=jdb(); c.execute("INSERT INTO jobs(id,uid,token,ts,status,credits,kind,label,file,err) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (jid,uid,t,int(time.time()),"running",cr,r.mode,label_for(r.mode,r.model,r.res,r.dur),None,None)); c.commit(); c.close()
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
    ext = os.path.splitext(file.filename or "img.png")[1][:6] or ".png"
    name = uuid.uuid4().hex[:10] + ext
    dst = os.path.join(d, name)
    with open(dst, "wb") as f: f.write(await file.read())
    return {"ref": os.path.relpath(dst, ROOT), "url": f"/api/upfile/{uid}/{name}", "name": file.filename}
@app.get("/api/upfile/{uid}/{name}")
def upfile(uid: str, name: str):
    p = os.path.join(UPLOADS, uid, os.path.basename(name))
    if not os.path.exists(p): raise HTTPException(404, "no file")
    return FileResponse(p)

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

class VoiceReq(BaseModel):
    text:str; voice_id:str=""
@app.post("/api/voice")
def voice(r: VoiceReq, authorization: str = Header(None)):
    """Voice-clone / TTS lane. Uses the character's 10s sample as the clone reference.
    Ready-to-wire: enable by setting VOICE_API_KEY (+ VOICE_API_BASE) for a clone TTS
    provider (e.g. ElevenLabs / Fish Audio / your seed-audio lane)."""
    auth_user(bearer(authorization))
    key = os.environ.get("VOICE_API_KEY")
    if not key:
        return {"file": None, "note": "Voice-clone lane is wired but off — set VOICE_API_KEY in Render env (ElevenLabs / Fish Audio / seed-audio) to go live. The 10s sample at /static/library/"+(r.voice_id or "<id>")+".mp3 is the clone reference."}
    # provider call goes here (kept generic); returns a hosted audio URL or served file
    return {"file": None, "note": "VOICE_API_KEY set — plug the provider call in server/app.py:voice()."}
@app.get("/config.js")
def cfg(): return HTMLResponse(f'window.SUPA_URL="{SUPA_URL}";window.SUPA_ANON="{SUPA_ANON}";', media_type="application/javascript")
app.mount("/static", StaticFiles(directory=os.path.join(SRV,"static")), name="static")
