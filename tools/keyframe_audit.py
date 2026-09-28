#!/usr/bin/env python3
"""Judge the whole keyframe SET in one look, not one image at a time.

Per-image QC cannot see the failure that actually ruins a film: the protagonist is a different
person in shot 2 than in shot 1, or the room teleports. Each frame passes on its own; the sequence
does not. Google's Co-Director (arXiv 2604.24842) measured this as the single largest contributor
in their ablation — removing joint keyframe verification cost more than removing anything else —
and the fix is to put the whole set in front of one judge at once.

For us this is free: images are ₹0 on the unlimited lanes, only video costs money. So the audit
runs before any Crun call, and only the frames it flags get regenerated.

  python3 tools/keyframe_audit.py sheet <proj> [--glob PATTERN] [--cols N]
        build the indexed contact sheet + the brief. Read BOTH, then judge.

  python3 tools/keyframe_audit.py verdict <proj> --score N --flag 3,7 [--note "..."]
        record a verdict. Champion semantics: a new set replaces the recorded best ONLY if it
        scores strictly higher, so refinement can never quietly make the film worse.

  python3 tools/keyframe_audit.py status <proj>
"""
import os, sys, json, glob, argparse, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THRESHOLD = 90          # Co-Director's own gate, out of 100
MAX_ATTEMPTS = 2        # and their own cap on refinement rounds

RUBRIC = [
    ("visual_consistency", 20, "Is it the SAME person in every frame they appear in — face, build, "
                               "hair, skin? Is the wardrobe the same garment, not merely a similar "
                               "one? Do props and set dressing persist?"),
    ("environment_continuity", 20, "Within a location, is it the same room — same walls, same light "
                                   "direction, same time of day? Flag teleportation."),
    ("narrative_flow", 20, "Read in order, do these frames tell the intended sequence? Does anything "
                           "jump a beat or repeat one?"),
    ("craft", 20, "Framing, focus, exposure, hands, faces. Anything that reads as a generation "
                  "artefact rather than a photograph."),
    ("prompt_adherence", 20, "Does each frame show what its shot actually asked for?"),
]

def project_dir(proj):
    return os.path.join(ROOT, "projects", proj)

def collect(proj, pattern):
    d = project_dir(proj)
    files = []
    for pat in pattern.split(","):
        files += glob.glob(os.path.join(d, pat.strip()))
    def key(f):
        import re
        m = re.findall(r"(\d+)", os.path.basename(f))
        return (int(m[0]) if m else 0, os.path.basename(f))
    return sorted(set(files), key=key)

def build_sheet(files, out, cols, tile=340):
    from PIL import Image, ImageDraw, ImageOps
    n = len(files); rows = (n + cols - 1) // cols
    th = int(tile * 9 / 16) if False else tile      # square cells, letterboxed
    pad, label = 6, 26
    W = cols * (tile + pad) + pad
    H = rows * (th + pad + label) + pad
    sheet = Image.new("RGB", (W, H), "#111318")
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        try:
            im = Image.open(f).convert("RGB")
        except Exception:
            continue
        im = ImageOps.contain(im, (tile, th))
        x = pad + (i % cols) * (tile + pad)
        y = pad + (i // cols) * (th + pad + label)
        sheet.paste(im, (x + (tile - im.width) // 2, y + (th - im.height) // 2))
        dr.rectangle([x, y + th, x + tile, y + th + label], fill="#C6452A")
        dr.text((x + 6, y + th + 7), f"[{i}]  {os.path.basename(f)[:38]}", fill="white")
    sheet.save(out, quality=90)
    return out, n, (W, H)

def brief(proj, files):
    d = project_dir(proj)
    lines = [f"JOINT KEYFRAME AUDIT · {proj} · {len(files)} frames",
             "",
             "Judge the SET, in one pass, in the order shown. The whole point is to catch what a",
             "per-image check cannot: the same character rendered as a different person between",
             "shots, wardrobe that changes garment, a room that teleports.",
             "",
             "Rubric — score each 0-20, total out of 100:"]
    for k, m, q in RUBRIC:
        lines += [f"  {k} (0-{m})", f"      {q}"]
    lines += ["",
              f"Gate: total >= {THRESHOLD} passes. Below that, name the frame INDICES to regenerate",
              f"      — not all of them, only the ones at fault. At most {MAX_ATTEMPTS} refinement rounds.",
              "",
              "Return exactly this, then record it with `keyframe_audit.py verdict`:",
              '  {"score": <0-100>, "problematic": [<indices>], "primary_fault": '
              '"<character|environment|narrative|craft|prompt>", "note": "<what to change>"}',
              "",
              "Frames, in order:"]
    for i, f in enumerate(files):
        rel = os.path.relpath(f, d)
        sid = os.path.splitext(os.path.basename(f))[0]
        doc = os.path.join(d, "docs", f"{sid.replace('cr_','').replace('_last','')}.txt")
        want = ""
        if os.path.exists(doc):
            t = open(doc, encoding="utf-8").read()
            for block in ("STARTING STATE", "SETTING"):
                if f"\n{block}\n" in t:
                    want = t.split(f"\n{block}\n", 1)[1].split("\n\n", 1)[0].strip().replace("\n", " ")
                    break
        lines.append(f"  [{i}] {rel}" + (f"\n        should show: {want[:150]}" if want else ""))
    return "\n".join(lines)

def state_path(proj):
    return os.path.join(project_dir(proj), "docs", "keyframe_audit.json")

def load_state(proj):
    p = state_path(proj)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"attempts": [], "champion": None}

def save_state(proj, st):
    p = state_path(proj); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(st, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("sheet"); s1.add_argument("proj")
    s1.add_argument("--glob", default="renders/cr_*_last.png,refs/*.png,refs/*.jpg")
    s1.add_argument("--cols", type=int, default=5)
    s2 = sub.add_parser("verdict"); s2.add_argument("proj")
    s2.add_argument("--score", type=int, required=True)
    s2.add_argument("--flag", default=""); s2.add_argument("--note", default="")
    s2.add_argument("--fault", default="")
    s3 = sub.add_parser("status"); s3.add_argument("proj")
    a = ap.parse_args()

    if a.cmd == "sheet":
        files = collect(a.proj, a.glob)
        if not files: sys.exit(f"no frames matched {a.glob} under projects/{a.proj}")
        out = os.path.join(project_dir(a.proj), "docs", "keyframe_sheet.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        out, n, size = build_sheet(files, out, a.cols)
        bp = os.path.join(project_dir(a.proj), "docs", "keyframe_brief.txt")
        open(bp, "w", encoding="utf-8").write(brief(a.proj, files))
        print(f"sheet  {out}   {n} frames, {size[0]}x{size[1]}")
        print(f"brief  {bp}")
        print("\nRead the sheet and the brief together, then record a verdict.")
        return

    st = load_state(a.proj)
    if a.cmd == "status":
        print(f"{a.proj}: {len(st['attempts'])} attempt(s), champion "
              f"{st['champion']['score'] if st['champion'] else 'none'}")
        for i, at in enumerate(st["attempts"]):
            print(f"  {i+1}. score {at['score']:3}  flagged {at['problematic']}  {at.get('note','')[:60]}")
        return

    flagged = [int(x) for x in a.flag.replace(" ", "").split(",") if x != ""]
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "score": a.score,
           "problematic": flagged, "primary_fault": a.fault, "note": a.note}
    st["attempts"].append(rec)
    ch = st["champion"]
    # Champion semantics: a later set must be strictly better to take over. Co-Director keeps the
    # best-scoring set rather than the latest, because refinement can and does regress.
    if ch is None or a.score > ch["score"]:
        st["champion"] = rec; verdict = "NEW CHAMPION"
    else:
        verdict = f"kept champion ({ch['score']}) — this attempt did not improve on it"
    save_state(a.proj, st)
    gate = "PASS" if a.score >= THRESHOLD and not flagged else "REGENERATE"
    print(f"recorded · score {a.score} · {verdict}")
    print(f"gate: {gate}" + (f" — frames {flagged}" if flagged else ""))
    if len(st["attempts"]) >= MAX_ATTEMPTS and gate == "REGENERATE":
        print(f"warn: {len(st['attempts'])} attempts, the cap is {MAX_ATTEMPTS}. "
              f"Stop refining and decide by hand.")
    sys.exit(0 if gate == "PASS" else 1)

if __name__ == "__main__":
    main()
