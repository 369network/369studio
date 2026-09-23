#!/usr/bin/env python3
"""studio369 clip ledger — one row per render attempt, per project.

Why this exists: clip state used to be smeared across renders/crun_state.json (task ids),
renders/crun_urls.json (upload cache), per-clip cr_<id>.mp4.json (credits) and the filenames
themselves. Nothing joined them, so we could not answer "what failed", "what did this project
cost", or "which clips are safe to chain from". 56% of clips had no cost record at all.

One SQLite file per repo: renders are still the source of truth on disk; this is the index.

  python3 tools/ledger.py backfill <proj>          rebuild rows from existing state + sidecars
  python3 tools/ledger.py backfill --all           every project under projects/
  python3 tools/ledger.py show <proj> [--all]      per-clip table (default: latest attempt each)
  python3 tools/ledger.py cost [<proj>]            spend per project, with coverage
  python3 tools/ledger.py failed <proj>            clip ids that need a retake
  python3 tools/ledger.py chain <proj>             chain readiness: which last-frames exist
  python3 tools/ledger.py record <proj> <clip> ... (used by run_crun.py; see --help)

Cost: Crun bills credits; CREDIT_USD converts for reporting only.
"""
import os, sys, json, sqlite3, time, glob, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(ROOT, "renders.db")
CREDIT_USD = 0.0048731              # 88.24 cr = $0.43 for a 10s 480p Crun clip
MIN_OK_BYTES = 400_000              # below this a downloaded mp4 is treated as truncated

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips(
  proj        TEXT NOT NULL,
  clip_id     TEXT NOT NULL,
  attempt     INT  NOT NULL DEFAULT 1,
  task_id     TEXT,
  status      TEXT,                  -- submitted | success | failed | truncated | missing
  lane        TEXT DEFAULT 'seedance_fast_crun',
  mode        TEXT,                  -- r2v | i2v | t2v
  res         TEXT, ar TEXT, dur INT,
  prompt_file TEXT,
  refs        TEXT,                  -- json list of ref paths sent
  chain_from  TEXT,                  -- clip_id whose last frame was used as a ref
  media_url   TEXT,
  last_frame_url TEXT,
  local_path  TEXT,
  last_frame_path TEXT,
  bytes       INT,
  duration_s  REAL,
  credits     REAL,
  submitted_at INT, finished_at INT,
  error       TEXT,
  PRIMARY KEY (proj, clip_id, attempt)
);
CREATE INDEX IF NOT EXISTS ix_clips_proj   ON clips(proj);
CREATE INDEX IF NOT EXISTS ix_clips_status ON clips(proj, status);
"""

def db():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=30000")
    c.executescript(SCHEMA); return c

def next_attempt(c, proj, clip_id):
    r = c.execute("SELECT MAX(attempt) a FROM clips WHERE proj=? AND clip_id=?", (proj, clip_id)).fetchone()
    return (r["a"] or 0) + 1

def upsert(proj, clip_id, attempt=None, **f):
    """Write or update one attempt. attempt=None updates the latest, creating attempt 1 if none."""
    c = db()
    if attempt is None:
        r = c.execute("SELECT MAX(attempt) a FROM clips WHERE proj=? AND clip_id=?", (proj, clip_id)).fetchone()
        attempt = r["a"] or 1
    c.execute("INSERT OR IGNORE INTO clips(proj,clip_id,attempt) VALUES(?,?,?)", (proj, clip_id, attempt))
    f = {k: v for k, v in f.items() if v is not None}
    if f:
        c.execute("UPDATE clips SET " + ",".join(f"{k}=?" for k in f) + " WHERE proj=? AND clip_id=? AND attempt=?",
                  list(f.values()) + [proj, clip_id, attempt])
    c.commit(); c.close(); return attempt

# ---------- probing ----------
def probe_seconds(path):
    try:
        import subprocess
        out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",path],
                             capture_output=True, text=True, timeout=30)
        return round(float(out.stdout.strip()), 2) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None

def classify(path):
    """(status, bytes, seconds). A file that exists but won't probe is 'truncated', not success —
    santan/_old_v1/cr_s3.mp4 was 196 KB, passed the old 100 KB guard and had no moov atom."""
    if not os.path.exists(path): return "missing", None, None
    n = os.path.getsize(path)
    if n < MIN_OK_BYTES: return "truncated", n, None
    s = probe_seconds(path)
    if s is None: return "truncated", n, None
    return "success", n, s

# ---------- backfill ----------
def backfill(proj):
    pdir = os.path.join(ROOT, "projects", proj)
    rdir = os.path.join(pdir, "renders")
    if not os.path.isdir(rdir): return 0
    state = {}
    sp = os.path.join(rdir, "crun_state.json")
    if os.path.exists(sp):
        try: state = json.load(open(sp))
        except Exception: state = {}
    scenes = {}
    for sf in ("scenes_A.json", "scenes.json"):
        p = os.path.join(pdir, sf)
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                # scenes_A.json is a dict keyed by scene number ("1","2",…); older files are a list.
                items = d.items() if isinstance(d, dict) and "scenes" not in d else \
                        [(None, s) for s in (d if isinstance(d, list) else d.get("scenes", []))]
                for k, s in items:
                    if not isinstance(s, dict): continue
                    sid = str(k if k is not None else (s.get("id") or s.get("sid") or ""))
                    if sid: scenes["s" + sid.lstrip("s")] = s
            except Exception: pass
            break

    # Clip files across every lane this repo has used. Assembly by-products are not clips.
    LANES = {"cr_":"seedance_fast_crun", "c2_":"protoface_h3", "sd_":"seedance", "sg_":"seedance",
             "vg_":"viggle_h3", "vg":"viggle_h3"}
    SKIP  = ("concat","mixed","subbed","final","proxy","preview")
    files = {}   # clip_id -> (path, lane)
    for f in sorted(glob.glob(os.path.join(rdir, "*.mp4"))):
        b = os.path.basename(f)[:-4]
        if b.endswith("_last") or any(b.startswith(s) for s in SKIP): continue
        if "_720p" in b or "_1080p" in b: continue
        lane = "unknown"
        for pre, ln in LANES.items():
            if b.startswith(pre): lane, b = ln, b[len(pre):]; break
        files.setdefault(b, (f, lane))

    # run_crun.py writes cr_<id with - turned into _>.mp4, so a manifest id "ah-01" lands on disk as
    # "cr_ah_01.mp4". Keying on the raw strings created TWO rows per clip and doubled every cost.
    # Canonical key = underscored; display id prefers the manifest spelling.
    def canon(x): return x.replace("-", "_")
    files = {canon(k): v for k, v in files.items()}
    display = {}
    for k in files: display.setdefault(canon(k), k)
    for k in state: display[canon(k)] = k          # manifest spelling wins
    state = {canon(k): v for k, v in state.items()}

    # A sidecar with no mp4 means we paid for a render and have nothing. That is the most
    # important row in the table, so surface it rather than dropping it.
    orphans = {}
    for j in sorted(glob.glob(os.path.join(rdir, "*.mp4.json"))):
        b = os.path.basename(j)[:-9]
        if any(b.startswith(s) for s in SKIP) or b.endswith("_last"): continue
        if os.path.exists(j[:-5]): continue
        for pre in LANES:
            if b.startswith(pre): b = b[len(pre):]; break
        orphans[canon(b)] = j

    seen = 0
    ids = sorted(set(state) | set(files) | set(orphans))

    for key in ids:
        cid = display.get(key, key)
        known = files.get(key)
        mp4  = known[0] if known else os.path.join(rdir, f"cr_{key}.mp4")
        lane = known[1] if known else "seedance_fast_crun"
        side = orphans.get(key) or (mp4 + ".json")
        lf   = os.path.join(rdir, f"cr_{key}_last.png")
        st   = state.get(key, {})
        credits = media = None; err = None; finished = None
        if os.path.exists(side):
            try:
                d = json.load(open(side))
                cr = d.get("credits")
                credits = float(cr) if isinstance(cr, (int, float)) else (
                    float(cr.get("charged")) if isinstance(cr, dict) and cr.get("charged") is not None else None)
                mus = (d.get("result") or {}).get("media_urls") or []
                media = mus[0] if mus else None
                finished = int(os.path.getmtime(side))
            except Exception: pass
        if st.get("error"):
            err = json.dumps(st["error"])[:300]
        status, nbytes, secs = classify(mp4)
        if status != "success" and err: status = "failed"
        sc = scenes.get(cid, {})
        upsert(proj, cid, attempt=1, lane=lane,
               task_id=st.get("tid"), status=status, media_url=media,
               local_path=os.path.relpath(mp4, ROOT) if os.path.exists(mp4) else None,
               last_frame_path=os.path.relpath(lf, ROOT) if os.path.exists(lf) else None,
               bytes=nbytes, duration_s=secs, credits=credits, finished_at=finished, error=err,
               chain_from=(f"s{sc['chain_from']}" if sc.get("chain_from") else None),
               refs=json.dumps(sc.get("chars")) if sc.get("chars") else None,
               prompt_file=f"docs/{cid}.txt" if os.path.exists(os.path.join(pdir, "docs", f"{cid}.txt")) else None)
        seen += 1
    return seen

# ---------- reports ----------
def latest_rows(c, proj):
    return c.execute("""SELECT * FROM clips c WHERE proj=? AND attempt=(
                          SELECT MAX(attempt) FROM clips WHERE proj=c.proj AND clip_id=c.clip_id)
                        ORDER BY LENGTH(clip_id), clip_id""", (proj,)).fetchall()

def cmd_show(a):
    c = db(); rows = c.execute("SELECT * FROM clips WHERE proj=? ORDER BY LENGTH(clip_id),clip_id,attempt", (a.proj,)).fetchall() if a.all else latest_rows(c, a.proj)
    if not rows: print(f"no rows for {a.proj} — run: ledger.py backfill {a.proj}"); return
    print(f"{'clip':10} {'try':3} {'status':10} {'secs':>6} {'MB':>6} {'cr':>7} {'chain':7} last-frame")
    for r in rows:
        mb = f"{r['bytes']/1e6:.1f}" if r["bytes"] else "-"
        print(f"{r['clip_id']:10} {r['attempt']:<3} {(r['status'] or '-'):10} "
              f"{(r['duration_s'] or 0):6.2f} {mb:>6} {(r['credits'] or 0):7.2f} "
              f"{(r['chain_from'] or '-'):7} {'yes' if r['last_frame_path'] else 'NO'}")
    c.close()

def cmd_cost(a):
    c = db()
    projs = [a.proj] if a.proj else [r["proj"] for r in c.execute("SELECT DISTINCT proj FROM clips ORDER BY proj")]
    print(f"{'project':20} {'clips':>6} {'ok':>4} {'bad':>4} {'credits':>10} {'USD':>8} {'metered':>9}")
    tc = tu = 0.0
    for p in projs:
        rows = latest_rows(c, p)
        cr = sum(r["credits"] or 0 for r in rows)
        ok = sum(1 for r in rows if r["status"] == "success")
        bad = len(rows) - ok
        met = sum(1 for r in rows if r["credits"] is not None)
        tc += cr; tu += cr * CREDIT_USD
        print(f"{p:20} {len(rows):6} {ok:4} {bad:4} {cr:10.1f} {cr*CREDIT_USD:8.2f} {met}/{len(rows):<6}")
    print(f"{'TOTAL':20} {'':6} {'':4} {'':4} {tc:10.1f} {tu:8.2f}")
    c.close()

def cmd_failed(a):
    c = db()
    rows = [r for r in latest_rows(c, a.proj) if r["status"] != "success"]
    if not rows: print(f"{a.proj}: all clips good"); return
    for r in rows: print(f"{r['clip_id']}\t{r['status']}\t{(r['error'] or '')[:100]}")
    print(f"\n{len(rows)} need a retake:\n  python3 tools/run_crun.py projects/{a.proj} <manifest> --retry " +
          " ".join(r["clip_id"] for r in rows), file=sys.stderr)
    c.close()

def cmd_chain(a):
    c = db(); rows = latest_rows(c, a.proj)
    by = {r["clip_id"]: r for r in rows}
    print(f"{'clip':10} {'status':10} {'needs':8} {'have?':6} ready")
    for r in rows:
        need = r["chain_from"] or "-"
        src = by.get(need)
        have = "-" if need == "-" else ("yes" if (src and src["last_frame_path"]) else "NO")
        ready = "ok" if (need == "-" or have == "yes") else "BLOCKED"
        print(f"{r['clip_id']:10} {(r['status'] or '-'):10} {need:8} {have:6} {ready}")
    c.close()

def cmd_backfill(a):
    projs = ([d for d in sorted(os.listdir(os.path.join(ROOT, "projects")))
              if os.path.isdir(os.path.join(ROOT, "projects", d, "renders"))] if a.all else [a.proj])
    for p in projs:
        n = backfill(p)
        if n: print(f"{p:20} {n} clips")

def cmd_record(a):
    kw = dict(task_id=a.task_id, status=a.status, media_url=a.media_url, last_frame_url=a.last_frame_url,
              local_path=a.local_path, last_frame_path=a.last_frame_path, credits=a.credits,
              prompt_file=a.prompt_file, refs=a.refs, chain_from=a.chain_from, mode=a.mode,
              res=a.res, ar=a.ar, dur=a.dur, error=a.error)
    if a.status == "submitted":
        c = db(); at = next_attempt(c, a.proj, a.clip) if a.new_attempt else None; c.close()
        kw["submitted_at"] = int(time.time())
        print(upsert(a.proj, a.clip, attempt=at, **kw))
    else:
        if a.local_path:
            full = os.path.join(ROOT, a.local_path)
            st, n, s = classify(full)
            kw["bytes"], kw["duration_s"] = n, s
            if a.status == "success" and st != "success": kw["status"] = st
        kw["finished_at"] = int(time.time())
        print(upsert(a.proj, a.clip, **kw))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("backfill"); p.add_argument("proj", nargs="?"); p.add_argument("--all", action="store_true"); p.set_defaults(f=cmd_backfill)
    p = sub.add_parser("show");     p.add_argument("proj"); p.add_argument("--all", action="store_true"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("cost");     p.add_argument("proj", nargs="?"); p.set_defaults(f=cmd_cost)
    p = sub.add_parser("failed");   p.add_argument("proj"); p.set_defaults(f=cmd_failed)
    p = sub.add_parser("chain");    p.add_argument("proj"); p.set_defaults(f=cmd_chain)
    p = sub.add_parser("record");   p.add_argument("proj"); p.add_argument("clip")
    for o in ("task-id","status","media-url","last-frame-url","local-path","last-frame-path",
              "prompt-file","refs","chain-from","mode","res","ar","error"): p.add_argument("--"+o)
    p.add_argument("--credits", type=float); p.add_argument("--dur", type=int)
    p.add_argument("--new-attempt", action="store_true"); p.set_defaults(f=cmd_record)
    a = ap.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
