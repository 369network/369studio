#!/usr/bin/env python3
"""The lane profile — model knowledge as data, and the two things you can do with it.

Adapted from Bench Studio's idea (MIT) that per-endpoint knowledge belongs in a hot-reloadable
JSON file rather than scattered through prose and code. Two consumers:

  validate(shot)  capability gate — is this request even legal for the lane, BEFORE we pay
  quote(shots)    cost estimate — what is this batch going to cost, BEFORE we say yes

The discipline that matters is in the profile, not here: a field is either measured from our own
ledger or flagged unverified, and anything we have never bought is UNQUOTABLE rather than guessed.
A wrong multiplier is worse than no number.

  python3 tools/lane_profile.py show
  python3 tools/lane_profile.py quote <proj> <manifest.json> [ids...]
  python3 tools/lane_profile.py check <proj> <manifest.json> [ids...]
"""
import os, sys, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(ROOT, "knowledge", "profiles", "seedance_fast_crun.json")

def load(path=DEFAULT):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------- capability

def validate(shot, prof=None):
    """Return a list of (severity, message). BLOCK = do not spend. warn = look, then decide.

    Severity is split on evidence, not on taste: violating something we have MEASURED blocks;
    using something merely DOCUMENTED but never exercised warns, because the profile is honest
    about not knowing.
    """
    p = prof or load()
    cap = p["capability"]
    out = []
    sid = shot.get("id", "?")

    dur = shot.get("dur")
    if dur is not None:
        d = int(dur)
        lo, hi = cap["duration_s"]["min"], cap["duration_s"]["max"]
        if d < lo or d > hi:
            out.append(("BLOCK", f"duration {d}s is outside the lane's {lo}-{hi}s range"))
        elif d not in cap["duration_s"]["verified"]:
            out.append(("warn", f"duration {d}s has never been run on this lane "
                                f"(verified: {cap['duration_s']['verified']})"))

    res = shot.get("res")
    if res:
        if res not in cap["resolution"]["options"]:
            out.append(("BLOCK", f"resolution {res} is not offered by the lane"))
        elif res not in cap["resolution"]["verified"]:
            out.append(("warn", f"resolution {res} has never been bought — cost is unquotable"))

    ar = shot.get("ar")
    if ar and ar not in cap["aspect_ratio"]["options"]:
        out.append(("BLOCK", f"aspect ratio {ar} is not offered by the lane"))

    refs = shot.get("refs") or []
    n = len(refs)
    if n > cap["max_refs"]["value"]:
        out.append(("BLOCK", f"{n} references exceeds the lane cap of {cap['max_refs']['value']} "
                             f"— run_crun.py will silently drop the extras"))
    elif n > cap["max_refs"]["verified_up_to"]:
        out.append(("warn", f"{n} references; we have only ever successfully sent "
                            f"{cap['max_refs']['verified_up_to']}"))

    mode = shot.get("mode")
    if mode == "T" or shot.get("endpoint") == "t2v":
        out.append(("warn", "t2v has never been run on this lane"))

    if mode == "A" and not shot.get("first"):
        out.append(("BLOCK", "mode A (i2v) needs a `first` frame"))
    if mode not in ("A", "T", None) and not refs:
        out.append(("BLOCK", "r2v with no references — nothing anchors identity"))

    return out

# ---------------------------------------------------------------- pricing

def quote_one(shot, prof=None):
    """(credits, usd, confidence). credits None = we refuse to quote."""
    p = prof or load()
    pr, cap = p["pricing"], p["capability"]
    res = shot.get("res") or cap["resolution"]["default"]
    dur = int(shot.get("dur") or 0)
    if res in pr.get("unquotable", []) or res not in cap["resolution"]["verified"]:
        return None, None, "unquotable"
    m = pr["model_480p"]           # fixed + per_second*dur — there is a small per-job component
    cr = round(m["fixed"] + m["per_second"] * dur, 2)
    return cr, round(cr * pr["credit_usd"], 4), pr["confidence"]

# Measured re-spend rate: 2 of 132 paid clips in renders.db were ever paid for twice.
# A point quote is the number that gets you overspent (juspay/director makes this point well),
# so quote a bracket — but derive every number, do not invent a safety factor.
RESPEND_RATE = 2 / 132

def quote(shots, prof=None):
    """(rows, best, expected, ceiling, unquotable_count) — all in credits and USD.

    best     nothing is retaken
    expected best plus the measured historical re-spend rate
    ceiling  every shot retaken once — the number to check a hard budget against
    """
    p = prof or load()
    rows, tot_cr, tot_usd, unq = [], 0.0, 0.0, 0
    for s in shots:
        cr, usd, conf = quote_one(s, p)
        rows.append((s.get("id", "?"), s.get("dur"), s.get("res") or p["capability"]["resolution"]["default"], cr, usd, conf))
        if cr is None: unq += 1
        else: tot_cr += cr; tot_usd += usd
    best = (round(tot_cr, 2), round(tot_usd, 4))
    exp  = (round(tot_cr * (1 + RESPEND_RATE), 2), round(tot_usd * (1 + RESPEND_RATE), 4))
    ceil_ = (round(tot_cr * 2, 2), round(tot_usd * 2, 4))
    return rows, best, exp, ceil_, unq

# ---------------------------------------------------------------- cli

def read_manifest(proj, manifest, ids):
    path = manifest if os.path.isabs(manifest) else os.path.join(ROOT, "projects", proj, manifest)
    if not os.path.exists(path):
        path2 = os.path.join(ROOT, "projects", proj, "docs", os.path.basename(manifest))
        path = path2 if os.path.exists(path2) else path
    M = json.load(open(path, encoding="utf-8"))
    if isinstance(M, dict): M = M.get("shots", [])
    return [m for m in M if not ids or m.get("id") in ids]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("show")
    for name in ("quote", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("proj"); sp.add_argument("manifest"); sp.add_argument("ids", nargs="*")
    a = ap.parse_args()
    p = load()

    if a.cmd == "show":
        print(f"{p['lane']} · {p['vendor']}")
        c = p["capability"]
        print(f"  duration    {c['duration_s']['min']}-{c['duration_s']['max']}s   verified {c['duration_s']['verified']}")
        print(f"  resolution  {c['resolution']['options']}   verified {c['resolution']['verified']}")
        print(f"  aspect      {c['aspect_ratio']['options']}")
        print(f"  refs        cap {c['max_refs']['value']}, verified up to {c['max_refs']['verified_up_to']}")
        m = p["pricing"]["model_480p"]
        print(f"  price       {m['fixed']} + {m['per_second']} cr/s at 480p "
              f"(~${m['per_second']*p['pricing']['credit_usd']:.4f}/s) · {p['pricing']['confidence']}")
        print(f"  prompt      {len(p['prompt']['required_blocks'])} required blocks, "
              f"{p['prompt']['ideal_length_words'][0]}-{p['prompt']['ideal_length_words'][1]} words")
        print(f"\n  {len(p['_meta']['unverified_flags'])} unverified flags:")
        for u in p["_meta"]["unverified_flags"]: print(f"    · {u}")
        return

    shots = read_manifest(a.proj, a.manifest, set(a.ids))
    if a.cmd == "quote":
        rows, best, exp, ceil_, unq = quote(shots, p)
        print(f"{'id':10}{'dur':>5}{'res':>8}{'credits':>10}{'usd':>9}  confidence")
        for sid, d, r, c_, u_, conf in rows:
            print(f"{sid:10}{str(d):>5}{r:>8}{('-' if c_ is None else f'{c_:.2f}'):>10}"
                  f"{('-' if u_ is None else f'{u_:.4f}'):>9}  {conf}")
        print(f"\n{len(rows)} shots" + (f" · {unq} unquotable" if unq else ""))
        print(f"  best      {best[0]:>9.2f} cr  ${best[1]:.2f}   nothing retaken")
        print(f"  expected  {exp[0]:>9.2f} cr  ${exp[1]:.2f}   + measured {RESPEND_RATE*100:.1f}% re-spend rate")
        print(f"  ceiling   {ceil_[0]:>9.2f} cr  ${ceil_[1]:.2f}   every shot retaken once")
        return

    bad = 0
    for s in shots:
        issues = validate(s, p)
        hard = [i for i in issues if i[0] == "BLOCK"]; bad += len(hard)
        print(f"{s.get('id','?'):10} {'BLOCK' if hard else ('warn' if issues else 'ok')}")
        for sev, m in issues: print(f"           {sev:5} {m}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
