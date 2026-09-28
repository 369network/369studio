#!/usr/bin/env python3
"""Turn a raw Crun/ByteDance failure into: what it is, what it cost, what to do next.

Every rule here was earned by a real failure in this studio, and each one records the credits
actually charged — because the single most useful thing to know when a render fails at 2am is
whether you just lost money. Pattern order matters: the specific causes are matched before the
generic ones, exactly as they are listed.

  python3 tools/crun_errors.py "<the error text>"
  from crun_errors import explain; explain(err_dict_or_str)
"""
import sys, json
import re

def _code(t, *codes):
    """True only if one of these HTTP codes appears as a status code, not as some other number.

    juspay/director lost two paid segments to exactly this: the message
    "must be 500 characters or less (got 503)" matched a bare \\b503\\b transient regex, so a
    non-retryable payload error was retried. Our own classifier had the same hole — "invalid
    duration: got 429 seconds" read as rate limiting, and "reference_images[403]" read as an auth
    failure. Both would have told you to --retry, which resubmits and pays again.
    """
    for c in codes:
        if re.search(r"(?:^|[^0-9a-z])(?:http[ /]?)?(?:status|code|error)?[ :=]*" + c + r"(?![0-9])"
                     r"(?=\s*(?:[:\-—,.)\]]|$|\s))", t):
            return True
    return False


# (name, matcher, charged, what it is, what to do)
RULES = [
    ("bad_request_not_retryable",
     lambda t: any(k in t for k in (
         "invalid parameter", "invalid duration", "invalid resolution", "invalid aspect",
         "is not a valid", "must be", "unsupported", "missing required", "validation error",
         "exceeds the maximum", "out of range")),
     "0 credits — and a retry will NOT help",
     "The request itself is wrong: a parameter the endpoint will never accept. This is the one "
     "class where retrying is actively harmful — it resubmits the same illegal payload and can "
     "bill for the attempt. It is also the class the pre-spend gate exists to catch, so a "
     "sighting here means `lane_profile` is missing a rule.",
     "Fix the manifest, then re-run `tools/preflight.py`. Add the constraint to "
     "knowledge/profiles/seedance_fast_crun.json so the gate blocks it next time. Do NOT --retry."),
    ("moderation_451",
     lambda t: _code(t, "451") or "moderation" in t or "content policy" in t or "risk control" in t,
     "0 credits",
     "Moderation. Seedance screens the INPUT and the OUTPUT, so a clean prompt can still fail on "
     "what it generated.",
     "Re-register the beat modestly — keep what happens, change how it is worded — and add an "
     "explicit no-contact negative. Do not simply resubmit; it will fail the same way. "
     "santan s10 went 0.95 -> 0.60 on the risk score this way and then rendered clean."),

    ("stale_reference_url",
     lambda t: "failed to download media" in t or "download media from the provided url" in t,
     "0 credits",
     "The vendor could not fetch a reference image. Nearly always a stale upload on our side, not "
     "a vendor fault: uguu deletes after about 3 hours and the URL cache used to hand out dead links.",
     "run_crun.py now expires cached upload URLs per host, so a plain --retry re-uploads. If it "
     "repeats, check CRUN_HOST and delete the entry from renders/crun_urls.json."),

    ("context_deadline",
     lambda t: "context deadline exceeded" in t or "read body err" in t,
     "0 credits",
     "Transient fetch timeout on the vendor side while pulling our reference. Not our payload.",
     "python3 tools/run_crun.py <proj> <manifest> --retry <id>. It cleared on the second attempt "
     "both times we hit it (santan s14, hisaab-ep04 002-06r)."),

    ("no_media_urls",
     lambda t: "no media_urls" in t or "success with no media" in t,
     "CHECK THE LEDGER — a success status with no output has been billed before",
     "The task reported success and returned nothing. This is the shape that produced our one "
     "orphan charge (afterhours/sd_04: 132.17 cr paid, no video).",
     "python3 tools/ledger.py show <proj> and look for `missing`. Raise it with the vendor if it "
     "was charged."),

    ("rate_limited",
     lambda t: _code(t, "429") or "rate limit" in t or "too many request" in t,
     "0 credits",
     "Rate limited.",
     "Wait and re-run; the runner is resumable, so nothing is lost and nothing is re-paid."),

    ("insufficient_credits",
     lambda t: "insufficient" in t or "not enough credit" in t or "balance" in t,
     "0 credits",
     "The account is out of credits.",
     "Top up. Every id already submitted keeps its task id in renders/crun_state.json, so "
     "re-running resumes rather than re-paying."),

    ("auth",
     lambda t: _code(t, "401", "403") or "unauthorized" in t or "invalid api key" in t,
     "0 credits",
     "Authentication rejected.",
     "Check ~/.config/keys_crun.env exists and is not empty. Never echo it. If it was pasted "
     "anywhere, rotate it."),

    ("truncated_download",
     lambda t: "truncated" in t or "moov atom not found" in t or "unplayable" in t,
     "0 credits to fix — the task id is still live",
     "The clip was generated and paid for; only our download is bad. Under 400 KB, or over the "
     "floor but with no moov atom (santan s21 arrived at 2.2 MB and would not decode).",
     "Delete the bad file and re-run WITHOUT --retry, so the runner re-downloads from the existing "
     "task id instead of resubmitting. --retry here would pay twice."),
]

GENERIC = ("unclassified", "unknown — check the ledger",
           "Not a failure shape we have seen before.",
           "Read the raw payload below, then add a rule here so the next person does not have to.")

def explain(err):
    raw = json.dumps(err, ensure_ascii=False) if not isinstance(err, str) else err
    t = raw.lower()
    for name, match, charged, what, todo in RULES:
        if match(t):
            return {"kind": name, "charged": charged, "what": what, "do": todo, "raw": raw}
    n, charged, what, todo = GENERIC
    return {"kind": n, "charged": charged, "what": what, "do": todo, "raw": raw}

def fmt(d, width=96):
    import textwrap
    out = [f"  {d['kind']}   (charged: {d['charged']})"]
    for label, key in (("what", "what"), ("do", "do")):
        for i, line in enumerate(textwrap.wrap(d[key], width)):
            out.append(f"    {label if i == 0 else '':5} {line}")
    return "\n".join(out)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("known failure shapes:")
        for name, _, charged, _, _ in RULES: print(f"  {name:22} charged: {charged}")
        sys.exit(0)
    print(fmt(explain(" ".join(sys.argv[1:]))))
