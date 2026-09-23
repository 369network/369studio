#!/usr/bin/env python3
"""The pre-spend gate. Run this before every render batch — nothing else.

Three checks that between them catch everything we have actually been burned by:

  1. run_crun.py --dry-run   every prompt file and every ref resolves, dur/refs in range
  2. ledger.py chain         the last-frame this clip chains from actually exists
  3. jev prompt-preflight    the PROMPT-STANDARD checklist, scored per shot

Exit 0 = safe to spend. Exit 1 = at least one BLOCK. Warnings never block on their own.

  python3 tools/preflight.py <proj> <manifest.json> [ids...]
  python3 tools/preflight.py santan shots.json --no-jev      skip the typed checks
  python3 tools/preflight.py santan shots.json --strict      warnings block too

Thresholds come from the measured distribution across santan s6-s26 (21 shots), not from taste:
ref_jobs 2.57-2.98, cast 2.99-3.00, ending 0.80-0.98, audio 2.91-2.98, face 0.24-0.36,
cinematic 0.11-0.15, moderation 0.02-0.39 with one real outlier at 0.95 that turned out to be a
genuine strike beat. So a moderation score above 0.70 blocks; the rest warn.
"""
import os, sys, json, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, ".claude", "skills", "jev", "packs", "prompt-preflight.json")

# (key, comparison, limit, severity, message)
RULES = [
    ("moderation_risk", ">", 0.70, "BLOCK", "reads as violent/intimate — 451 risk, and a 451 mid-chain stops everything after it"),
    ("beats",           "!=", "three", "warn", "a 10s shot wants exactly three beats"),
    ("face_text",       ">", 0.60, "warn", "describes a face while a plate is attached — the text competes with the plate and loses"),
    ("cinematic_word",  ">", 0.50, "warn", "'cinematic' / trailer vocabulary pulls toward a rendered CGI look"),
    ("ref_jobs",        "<", 2.50, "warn", "a ref is missing its one job or its do-not-copy clause"),
    ("cast_block",      "<", 2.50, "warn", "CAST does not close the frame edges — the model will invent a person"),
    ("ending_state",    "<", 0.60, "warn", "ENDING STATE thin or missing — it is the next clip's continuity ref"),
    ("audio_block",     "<", 2.50, "warn", "AUDIO not positive-first, or the exclusion list is incomplete"),
]

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)

def dry_run(proj, manifest, only):
    r = run([sys.executable, "tools/run_crun.py", f"projects/{proj}", manifest, "--dry-run"] + list(only))
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip()[:300]
    rows = {}
    for line in r.stdout.splitlines():
        p = line.split()
        if not p or "prompt=" not in line: continue
        sid = p[0]
        rows[sid] = {
            "prompt_ok": "prompt=OK" in line,
            "missing_refs": line.split("missing_refs=", 1)[1].strip() if "missing_refs=" in line else "[]",
        }
    return rows, None

def chain(proj):
    r = run([sys.executable, "tools/ledger.py", "chain", proj])
    blocked = set()
    for line in r.stdout.splitlines()[1:]:
        p = line.split()
        if len(p) >= 5 and p[-1] == "BLOCKED": blocked.add(p[0])
    return blocked

def jev_one(prompt_path):
    r = run([sys.executable, "tools/jev.py", "ask", "--state-file", prompt_path,
             "--questions", PACK, "--json"])
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip().splitlines()[0][:160]
    try:
        d = json.loads(r.stdout)
    except Exception:
        return None, "unparseable jev response"
    out = {}
    for qid, a in (d.get("answers") or {}).items():
        out[qid] = a.get("choice") if a.get("type") == "choice" else (
            a.get("score") if a.get("type") == "score" else a.get("noul"))
        out[qid + "__conf"] = a.get("confidence")
    out["__cost"] = (d.get("usage") or {}).get("cost")
    return out, None

def judge(vals):
    hits = []
    for key, op, lim, sev, msg in RULES:
        v = vals.get(key)
        if v is None: continue
        bad = (v > lim) if op == ">" else (v < lim) if op == "<" else (v != lim)
        if bad:
            c = vals.get(key + "__conf")
            hits.append((sev, key, v, c, msg))
    return hits

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj"); ap.add_argument("manifest"); ap.add_argument("ids", nargs="*")
    ap.add_argument("--no-jev", action="store_true", help="skip the typed checks (no key, or offline)")
    ap.add_argument("--strict", action="store_true", help="warnings block too")
    a = ap.parse_args()

    print(f"pre-spend gate · {a.proj} · {a.manifest}\n")

    rows, err = dry_run(a.proj, a.manifest, a.ids)
    if rows is None:
        print(f"BLOCK  dry-run failed: {err}"); sys.exit(1)
    blocked = chain(a.proj)

    blocks = warns = 0; cost = 0.0
    for sid, d in rows.items():
        issues = []
        if not d["prompt_ok"]: issues.append(("BLOCK", "prompt file missing"))
        if d["missing_refs"] not in ("[]", ""): issues.append(("BLOCK", f"missing refs {d['missing_refs']}"))
        if sid in blocked: issues.append(("BLOCK", "chain ref does not exist yet"))

        if not a.no_jev and d["prompt_ok"]:
            pf = os.path.join(ROOT, "projects", a.proj, "docs", f"{sid}.txt")
            if os.path.exists(pf):
                vals, jerr = jev_one(pf)
                if jerr:
                    issues.append(("warn", f"jev unavailable ({jerr})"))
                else:
                    cost += vals.get("__cost") or 0
                    for sev, key, v, c, msg in judge(vals):
                        conf = f" conf={c:.2f}" if isinstance(c, float) else ""
                        issues.append((sev, f"{key}={v}{conf} — {msg}"))

        hard = [i for i in issues if i[0] == "BLOCK"]
        soft = [i for i in issues if i[0] == "warn"]
        blocks += len(hard); warns += len(soft)
        verdict = "BLOCK" if hard else ("warn" if soft else "ok")
        print(f"{sid:8} {verdict}")
        for sev, m in issues:
            print(f"         {sev:5} {m}")

    print()
    if cost: print(f"jev: ${cost:.6f}")
    print(f"{blocks} blocking · {warns} warnings")
    if blocks or (a.strict and warns):
        print("\nDo not spend. Fix the blocking items, then re-run this gate.")
        sys.exit(1)
    print("\nSafe to spend:")
    ids = " ".join(a.ids) if a.ids else ""
    print(f"  python3 tools/run_crun.py projects/{a.proj} {a.manifest} {ids}".rstrip())
    sys.exit(0)

if __name__ == "__main__":
    main()
