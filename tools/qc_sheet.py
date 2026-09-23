#!/usr/bin/env python3
"""Contact sheet + hard checks for rendered clips — replaces tools/bench_qc.py.

bench_qc.py globbed `vg*_` and `c2_` (viggle / protoface) and was hard-wired to projects/bench,
so it was structurally blind to every `cr_*.mp4` made since 15 Sep — i.e. to the only lane we use.
This works on any project and any lane.

  python3 tools/qc_sheet.py <proj> [ids...]     one 1-fps tile strip per clip + a stacked sheet
  python3 tools/qc_sheet.py <proj> --check      no images: just the pass/fail table
  python3 tools/qc_sheet.py <proj> --black      also report black-frame runs (tail fades)

Writes projects/<proj>/renders/qc/<clip>.jpg and renders/qc/_sheet.jpg
Exit code 1 if any clip fails a hard check, so it can gate a script.
"""
import subprocess, os, sys, glob, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_OK = int(os.environ.get("CRUN_MIN_BYTES", "400000"))
SKIP = ("concat", "mixed", "subbed", "final", "proxy", "preview")

def sh(*a, t=120):
    return subprocess.run(a, capture_output=True, text=True, timeout=t)

def probe(f):
    r = sh("ffprobe", "-v", "error", "-show_entries",
           "format=duration:stream=width,height,codec_type", "-of", "json", f)
    if r.returncode != 0: return None
    try: d = json.loads(r.stdout)
    except Exception: return None
    st = d.get("streams") or []
    return {"secs": float((d.get("format") or {}).get("duration") or 0),
            "w": next((s.get("width") for s in st if s.get("codec_type") == "video"), None),
            "h": next((s.get("height") for s in st if s.get("codec_type") == "video"), None),
            "audio": any(s.get("codec_type") == "audio" for s in st)}

def black_tail(f):
    """A clip that ends in black reads to the viewer as a bug — we shipped one at 1:29 once."""
    r = sh("ffmpeg", "-v", "info", "-i", f, "-vf", "blackdetect=d=0.5:pic_th=0.98", "-f", "null", "-")
    out = []
    for line in (r.stderr or "").splitlines():
        if "black_start" in line:
            try:
                st = float(line.split("black_start:")[1].split()[0])
                en = float(line.split("black_end:")[1].split()[0]) if "black_end:" in line else None
                out.append((st, en))
            except Exception: pass
    return out

def clips(proj, only):
    rd = os.path.join(ROOT, "projects", proj, "renders")
    out = []
    for f in sorted(glob.glob(os.path.join(rd, "*.mp4"))):
        b = os.path.basename(f)[:-4]
        if b.endswith("_last") or any(b.startswith(s) for s in SKIP): continue
        if "_720p" in b or "_1080p" in b: continue
        cid = b.split("_", 1)[1] if b.split("_", 1)[0] in ("cr", "c2", "sd", "sg", "vg") else b
        if only and cid not in only and b not in only: continue
        out.append((cid, f))
    return out

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    proj = sys.argv[1]
    args = sys.argv[2:]
    CHECK = "--check" in args
    BLACK = "--black" in args
    only = set(a for a in args if not a.startswith("-"))
    rd = os.path.join(ROOT, "projects", proj, "renders")
    qd = os.path.join(rd, "qc"); os.makedirs(qd, exist_ok=True)

    found = clips(proj, only)
    if not found: sys.exit(f"no clips in projects/{proj}/renders")

    rows, bad = [], 0
    for cid, f in found:
        n = os.path.getsize(f)
        p = probe(f)
        issues = []
        if n < MIN_OK: issues.append(f"TRUNCATED {n//1024}KB")
        if not p:      issues.append("UNREADABLE (moov atom?)")
        else:
            if p["secs"] < 2: issues.append(f"too short {p['secs']:.1f}s")
            if not p["audio"]: issues.append("no audio track")
        if BLACK and p:
            for st, en in black_tail(f):
                if en is None or en >= p["secs"] - 0.2:
                    issues.append(f"BLACK TAIL from {st:.1f}s"); break
        lf = os.path.join(rd, f"cr_{cid}_last.png")
        if not os.path.exists(lf): issues.append("no last-frame (chain breaks here)")
        rows.append((cid, n, p, issues))
        if issues: bad += 1

        if not CHECK and p and n >= MIN_OK:
            jpg = os.path.join(qd, f"{cid}.jpg")
            if not os.path.exists(jpg):
                sh("ffmpeg", "-v", "error", "-y", "-i", f, "-vf",
                   "fps=1,scale=220:-1,tile=8x1", "-frames:v", "1", jpg, t=300)

    print(f"{'clip':14} {'MB':>6} {'secs':>6} {'WxH':>10} {'aud':>4}  issues")
    for cid, n, p, issues in rows:
        dims = f"{p['w']}x{p['h']}" if p else "-"
        secs = p["secs"] if p else 0.0
        aud  = "yes" if (p and p["audio"]) else "NO"
        print(f"{cid:14} {n/1e6:6.1f} {secs:6.2f} {dims:>10} {aud:>4}  {'; '.join(issues) or 'ok'}")

    if not CHECK:
        try:
            from PIL import Image, ImageDraw
            ims = []
            for cid, n, p, _ in rows:
                jpg = os.path.join(qd, f"{cid}.jpg")
                if not os.path.exists(jpg): continue
                im = Image.open(jpg).convert("RGB")
                ImageDraw.Draw(im).text((6, 6), cid, fill="yellow")
                ims.append(im)
            if ims:
                sheet = Image.new("RGB", (max(i.width for i in ims), sum(i.height + 6 for i in ims)), "white")
                y = 0
                for i in ims: sheet.paste(i, (0, y)); y += i.height + 6
                out = os.path.join(qd, "_sheet.jpg"); sheet.save(out, quality=70)
                print("\nsheet:", os.path.relpath(out, ROOT), sheet.size)
        except ImportError:
            print("\n(PIL not installed — per-clip strips written, no stacked sheet)")

    print(f"\n{len(rows) - bad}/{len(rows)} clean")
    if bad:
        ids = " ".join(c for c, _, _, i in rows if i)
        print(f"retry: python3 tools/run_crun.py projects/{proj} <manifest> --retry {ids}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
