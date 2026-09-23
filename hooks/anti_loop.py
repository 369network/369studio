#!/usr/bin/env python3
"""PreToolUse hook — LoopGuard. Same tool + same substantive args 3x within the last 5 calls → block (exit 2).

Fixed 23 Sep 2026 (system audit):
  - RESUMABLE RUNNERS ARE EXEMPT. RUNBOOK §O says "the runner is resumable, so just re-invoke",
    and §N's recovery is to re-submit a cleared id. Those are identical Bash calls by design, and
    the guard was blocking the documented recovery procedure on the third try.
  - The history file is parsed defensively. A blank or half-written line used to raise
    JSONDecodeError, which crashed the hook instead of allowing the call.
  - Writes are atomic (tmp + replace) so a parallel batch cannot interleave into a corrupt file.
"""
import sys, json, os, hashlib, time, tempfile

P = os.path.expanduser('~/.cache/studio369-loopguard.jsonl')
os.makedirs(os.path.dirname(P), exist_ok=True)

# Tools that are read-only or idempotent by nature.
EXEMPT_TOOLS = ('Read', 'Glob', 'Grep', 'AskUserQuestion', 'TodoWrite')

# Commands built to be re-run until they finish. Blocking these breaks the recovery path.
RESUMABLE = ('run_crun.py', 'santan_run.py', 'run_atlas_img.py', 'ledger.py',
             'qc_sheet.py', 'post.py', 'plan.py')

def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    name = ev.get('tool_name', '')
    inp = ev.get('tool_input', {}) or {}
    if name in EXEMPT_TOOLS:
        sys.exit(0)

    if name == 'Bash':
        cmd = str(inp.get('command', ''))
        if any(r in cmd for r in RESUMABLE):
            sys.exit(0)

    norm = json.dumps(inp, sort_keys=True)[:4000].lower()
    fp = hashlib.sha1((name + '|' + norm).encode()).hexdigest()

    hist = []
    if os.path.exists(P):
        try:
            with open(P) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        h = json.loads(line)
                        if isinstance(h, dict) and 'fp' in h and 't' in h:
                            hist.append(h)
                    except Exception:
                        continue          # a torn line is not a reason to fail the call
        except Exception:
            hist = []

    now = time.time()
    hist = [h for h in hist if now - h['t'] < 1800][-4:]

    if sum(1 for h in hist if h['fp'] == fp) >= 2:
        print(f'LoopGuard blocked: {name} called with the same substantive args 3x in the last '
              f'5 calls. Change tool/model/prompt substantively, or stop and ask the user.',
              file=sys.stderr)
        sys.exit(2)

    hist.append({'fp': fp, 't': now})
    try:
        d = os.path.dirname(P)
        fd, tmp = tempfile.mkstemp(dir=d, prefix='.lg-')
        with os.fdopen(fd, 'w') as f:
            f.write(''.join(json.dumps(h) + '\n' for h in hist))
        os.replace(tmp, P)
    except Exception:
        pass
    sys.exit(0)

if __name__ == '__main__':
    main()
