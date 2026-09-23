#!/usr/bin/env python3
"""Jev (TypeSafe AI System One) — typed text decisions for studio369.

Jev answers a batch of typed questions about a block of state and returns a TYPE, not prose:
  choice  -> one of your options, with per-option probabilities
  score   -> a position on your scale, with a legend
  noul    -> a 0..1 likelihood

Use it where the system currently guesses in prose: triaging a QC failure, routing a retake,
scoring prompt-standard compliance, classifying a moderation rejection. It CANNOT look at an
image or a video — every visual judgement stays with the qc agent.

  python3 tools/jev.py ping
  python3 tools/jev.py ask --state-file s.txt --questions q.json [--model jev-latest]
  python3 tools/jev.py ask --state "some text" --questions q.json --json
  python3 tools/jev.py cost                       running spend from the local log

questions.json is the API's own shape — an OBJECT keyed by your question ids:
  {
    "lane":   {"type":"choice","instructions":"Which lane?","criteria":{"crun":"video","topview":"image"}},
    "sev":    {"type":"score","instructions":"How bad?","criteria":["cosmetic","reshoot","blocker"]},
    "retake": {"type":"noul","instructions":"Should we spend credits on a retake?"}
  }

Key: JEV_API_KEY, from the env or ~/.config/keys_jev.env. Never printed, never in argv
(passed through a 0600 `curl -K` config that is deleted on exit).

Cost: $0.042 per 1M input tokens, output free. Limits: 255 choice options, 2-10 score levels,
250k tokens/sec and 1,200 requests/MINUTE. Batch many questions into ONE call — TypeSafe's own
cookbook measures 13 batched questions as 12.2x cheaper and 10x faster than 13 calls.
"""
import os, sys, json, time, argparse, subprocess, tempfile, atexit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.typesafe.ai/v1/systemone"
USD_PER_INPUT_TOKEN = 0.042 / 1_000_000          # output is free
LOG = os.path.join(ROOT, "renders", "jev_log.jsonl")

def load_key():
    k = os.environ.get("JEV_API_KEY")
    for p in (os.path.expanduser("~/.config/keys_jev.env"), os.path.join(ROOT, ".config", "keys_jev.env")):
        if not k and os.path.exists(p):
            for line in open(p):
                if line.startswith("JEV_API_KEY="):
                    k = line.strip().split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("JEV_API_KEY missing.\n"
                 "  Get an official key at https://console.typesafe.ai (open signup, no waitlist)\n"
                 "  then:  printf 'JEV_API_KEY=...\\n' > ~/.config/keys_jev.env && chmod 600 ~/.config/keys_jev.env\n"
                 "  Do NOT use a jevai.org key — that is an unofficial proxy and 401s here.")
    return k

_CFG = None
def hdr_cfg(key):
    """Auth header in a 0600 file, not argv — argv is readable by any local process via ps."""
    global _CFG
    if _CFG is None:
        fd, _CFG = tempfile.mkstemp(prefix=".jev-", suffix=".conf"); os.close(fd)
        os.chmod(_CFG, 0o600)
        with open(_CFG, "w") as f:
            f.write(f'header = "Authorization: Bearer {key}"\nheader = "Content-Type: application/json"\n')
        atexit.register(lambda: os.path.exists(_CFG) and os.remove(_CFG))
    return _CFG

def call(state, questions, model="jev-latest", tries=4):
    key = load_key()
    body = {"state": state, "model": model, "questions": questions}
    bf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(body, bf, ensure_ascii=False); bf.close()
    atexit.register(lambda p=bf.name: os.path.exists(p) and os.remove(p))
    delay = 1.5
    for attempt in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "120", "-w", "\n%{http_code}",
                            "-K", hdr_cfg(key), "-X", "POST", "--data-binary", f"@{bf.name}", API],
                           capture_output=True, text=True)
        raw = r.stdout or ""
        code = raw.rsplit("\n", 1)[-1].strip()
        payload = raw.rsplit("\n", 1)[0]
        if code == "200":
            try: d = json.loads(payload)
            except Exception: sys.exit(f"200 but unparseable body: {payload[:300]}")
            _log(d, questions)
            return d
        if code in ("429", "529") and attempt < tries - 1:     # documented: exponential backoff
            print(f"jev {code}, retrying in {delay:.1f}s ({attempt+1}/{tries})", file=sys.stderr)
            time.sleep(delay); delay *= 2; continue
        hint = {"401": "invalid key — get an official one at console.typesafe.ai; a jevai.org key will not work",
                "422": "malformed body — questions must be an OBJECT keyed by id; choice criteria is a map, score criteria is a list of 2-10 levels",
                "429": "rate limited (limit is 1,200 requests/MINUTE — you are probably looping)",
                "529": "TypeSafe overloaded"}.get(code, "")
        sys.exit(f"jev HTTP {code}{': ' + hint if hint else ''}\n{payload[:400]}")

def _log(d, questions):
    u = d.get("usage") or {}
    rec = {"ts": int(time.time()), "questions": len(questions),
           "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
           "usd": round((u.get("input_tokens") or 0) * USD_PER_INPUT_TOKEN, 8)}
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    except Exception: pass

def fmt(d):
    out = []
    for qid, a in (d.get("answers") or {}).items():
        t = a.get("type")
        if t == "choice":
            probs = a.get("probabilities") or {}
            top = " ".join(f"{k}={v:.2f}" for k, v in sorted(probs.items(), key=lambda x: -x[1])[:4])
            out.append(f"{qid:20} choice  {a.get('choice')}   conf={a.get('confidence'):.2f}   {top}"
                       if a.get("confidence") is not None else
                       f"{qid:20} choice  {a.get('choice')}   {top}")
        elif t == "score":
            leg = a.get("legend") or {}
            near = leg.get(str(int(round(a.get("score", 0))))) or ""
            c = a.get("confidence")
            out.append(f"{qid:20} score   {a.get('score'):.2f}  ({near})" + (f"   conf={c:.2f}" if c is not None else ""))
        else:
            out.append(f"{qid:20} noul    {a.get('noul'):.3f}")
    u = d.get("usage") or {}
    out.append(f"\n{u.get('input_tokens', 0)} input tokens = "
               f"${(u.get('input_tokens') or 0) * USD_PER_INPUT_TOKEN:.6f}  (output free)")
    return "\n".join(out)

def cmd_ping(a):
    q = {"reachable": {"type": "noul", "instructions": "Is this sentence in English?"}}
    d = call("The quick brown fox jumps over the lazy dog.", q, a.model)
    print("jev OK —", json.dumps(d.get("answers"), separators=(",", ":")))
    print(f"model: {d.get('model')}   usage: {d.get('usage')}")

def cmd_ask(a):
    state = a.state if a.state else open(a.state_file, encoding="utf-8").read()
    questions = json.load(open(a.questions, encoding="utf-8"))
    if not isinstance(questions, dict):
        sys.exit("questions must be an OBJECT keyed by question id, not a list")
    for qid, q in questions.items():
        t = q.get("type")
        if t == "choice" and not isinstance(q.get("criteria"), dict):
            sys.exit(f"{qid}: choice criteria must be an object {{option: description}}")
        if t == "score":
            c = q.get("criteria")
            if not isinstance(c, list) or not (2 <= len(c) <= 10):
                sys.exit(f"{qid}: score criteria must be a list of 2-10 levels")
        if t == "choice" and len(q.get("criteria") or {}) > 255:
            sys.exit(f"{qid}: choice allows at most 255 options")
    d = call(state, questions, a.model)
    print(json.dumps(d, indent=1, ensure_ascii=False) if a.json else fmt(d))

def cmd_cost(a):
    if not os.path.exists(LOG): print("no jev calls logged yet"); return
    n = tok = 0; usd = 0.0
    for line in open(LOG):
        try: r = json.loads(line)
        except Exception: continue
        n += 1; tok += r.get("input_tokens") or 0; usd += r.get("usd") or 0
    print(f"{n} calls · {tok:,} input tokens · ${usd:.4f} total (output free)")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="jev-latest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping").set_defaults(f=cmd_ping)
    p = sub.add_parser("ask")
    p.add_argument("--state"); p.add_argument("--state-file"); p.add_argument("--questions", required=True)
    p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_ask)
    sub.add_parser("cost").set_defaults(f=cmd_cost)
    a = ap.parse_args()
    if a.cmd == "ask" and not (a.state or a.state_file): ap.error("need --state or --state-file")
    a.f(a)

if __name__ == "__main__":
    main()
