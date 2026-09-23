---
name: jev
description: Turn a judgement call into a typed answer instead of prose — route a retake, triage a QC failure, score prompt-standard compliance, classify a moderation rejection, rank a batch. Use whenever the system is about to decide something in free text that would be more reliable as a choice / score / probability, and whenever a decision is repeated over many items. Text only — Jev cannot see an image or a video, so every visual judgement stays with the `qc` agent. Triggers: "jev", "typesafe", "triage this", "which lane", "score these", "classify", "should we retake", "rank these".
---

# Jev — typed decisions (TypeSafe AI System One)

`tools/jev.py`. One POST returns a **type**, not a paragraph: a `choice` from your options with
per-option probabilities, a `score` on your scale with a legend, or a `noul` likelihood 0–1.

The point is not that Jev is smarter — **it is not**. On TypeSafe's own published evals it sits
mid-pack (67.8%, level with Sonnet 5, ~6 points below Opus 5). The point is that the answer is
*shaped*: it cannot come back as "it depends", it carries a confidence number, it costs
~$0.000004 per decision, and it returns in ~0.24 s. That makes it right for decisions you make
**hundreds of times**, and wrong for the one hard call of the day — make that one yourself.

## When to reach for it

| Good fit | Why |
|---|---|
| Triaging a QC failure across 26 clips | same question, many items, needs a consistent label |
| "Retake or accept?" on a marginal clip | a probability beats a paragraph, and it is auditable |
| Scoring a prompt against PROMPT-STANDARD before spend | 10 checks in one call, cheap enough to run every time |
| Classifying a `451` rejection (input vs output, which trigger) | a fixed taxonomy, repeated |
| Ranking 40 scene drafts | batch of scores, one call |

## When NOT to

- **Anything visual.** Images, audio and video are "not supported (yet)". Frame QC, identity
  drift, costume strip, black tails — all of that stays in `.claude/agents/qc.md`.
- **Counting, dates, arithmetic, indirection, large noisy state** — TypeSafe documents these as
  weaknesses. Do the arithmetic in Python and hand Jev the result.
- **A single novel judgement.** You are better at it. Use Jev for volume and consistency.
- **Anything where being wrong is expensive and unreviewed.** "Zero hallucinations" means zero
  *out-of-schema* output — TypeSafe states it is a type-safety claim, not a correctness one. A
  confident wrong answer is still a wrong answer.

## Using it

```bash
python3 tools/jev.py ping                                   # auth + reachability
python3 tools/jev.py ask --state-file docs/s6.txt \
                         --questions .claude/skills/jev/packs/prompt-preflight.json
python3 tools/jev.py ask --state "<the failure text>" \
                         --questions .claude/skills/jev/packs/qc-triage.json --json
python3 tools/jev.py cost                                   # running spend
```

`--questions` is the API's own shape: an **object keyed by your question ids**.

```json
{
  "lane":   {"type":"choice","instructions":"Which lane?",
             "criteria":{"crun":"video","topview":"free image","atlas":"paid image, edit-with-refs"}},
  "sev":    {"type":"score","instructions":"How bad is this?",
             "criteria":["cosmetic","needs a retake","blocks the chain"]},
  "retake": {"type":"noul","instructions":"Is spending credits on a retake justified?"}
}
```

- `choice` → `criteria` is a **map** of option → description. Max **255**.
- `score` → `criteria` is a **list** of 2–10 ordered levels.
- `noul` → no criteria; returns 0–1.

`tools/jev.py` validates all three before spending a call, so a malformed pack fails locally
instead of coming back as a 422.

## The one rule that matters: batch

Ask every question you have about one piece of state in **one** call. TypeSafe's own cookbook
measures 13 batched questions as **12.2× cheaper and 10× faster** than 13 separate calls, with
identical answers. The state is what costs; the questions are nearly free.

Do not loop one call per clip if one call can carry the whole batch's state. The limit is 1,200
requests **per minute**, so a loop will not hit the ceiling — it will just cost 12× more and take
10× longer for no benefit.

## Ready-made packs

- `packs/prompt-preflight.json` — the PROMPT-STANDARD checklist as 8 typed checks. Run it on a
  `docs/s<N>.txt` before any spend; pair it with `run_crun.py --dry-run` and `ledger.py chain`.
- `packs/qc-triage.json` — given a failure description, what class of failure, how severe,
  retake or accept, and which fix applies.
- `packs/moderation-451.json` — input-side or output-side, likely trigger, suggested rewrite axis.

Copy a pack and edit it; they are plain JSON.

## Cost and limits

$0.042 per 1M **input** tokens, output free. A prompt-preflight call on a 4 KB shot doc is about
1,200 tokens ≈ **$0.00005**. Running it on all 101 santan scenes costs about half a cent.
Realistic monthly spend for this studio: **$1–5**.

250k tokens/sec, 1,200 requests/minute. No SLA. Prepaid credits expire after 12 months.

## Key — either route works

Same model, same request shape, two front doors. `tools/jev.py` uses whichever key it finds and
prefers OpenRouter (it returns a real per-call `usage.cost`). Force one with `--via`.

| Route | Key | File | Endpoint |
|---|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` (`sk-or-v1-…`) | `~/.config/keys_openrouter.env` | `openrouter.ai/api/v1/systemone` |
| TypeSafe direct | `JEV_API_KEY` | `~/.config/keys_jev.env` | `api.typesafe.ai/v1/systemone` |

```bash
printf 'OPENROUTER_API_KEY=sk-or-v1-...\n' > ~/.config/keys_openrouter.env && chmod 600 ~/.config/keys_openrouter.env
```

Keys are never printed and never in argv — a 0600 `curl -K` config, deleted on exit.

Verified, not assumed: `POST openrouter.ai/api/v1/systemone` answers `401` exactly as the known
route `/api/v1/chat/completions` does, while a made-up path answers `404` — so the Decisions route
is real. Jev does **not** appear in `GET /api/v1/models`; that catalogue lists chat-completions
models and Jev is not one, so its absence is expected and not a problem.

**Never use a jevai.org key** — unofficial proxy, anonymously registered domain, 401s on both
routes and its own quota dies after about five calls.

Full evaluation, including why the first version of our notes was wrong about the rate limit:
project doc `claude/jev-typesafe-evaluation.md`.
