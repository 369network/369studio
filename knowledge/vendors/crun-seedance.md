---
vendor: crun-seedance
modality: video
status: active
provider: crun.ai (ByteDance Seedance 2.0 FAST)
backend: crun
lane: seedance_fast_crun
runner: tools/run_crun.py
---

# crun-seedance — the video lane

**This is the only live video lane.** Every shot goes here. Read this card before composing or changing any
video prompt. The prompt itself is governed by `knowledge/PROMPT-STANDARD.md`, not by this card — this card is
the transport, the limits and the failure list.

## API

- Base: `https://api.crun.ai/api/v1/client/job`
  - `POST {base}/CreateTask` — body below → `data.task_id`
  - `GET  {base}/TaskInfo?task_id=<tid>` → `data.status` ∈ `success | failed | <in-progress>`, `data.result.media_urls`, `data.credits`
- Auth header: **`x-api-key: <CRUN_KEY>`** (not Bearer), plus `Content-Type: application/json`.
- Key resolution in the runner: `$CRUN_KEY` → `~/.config/keys_crun.env` → `<root>/.config/keys_crun.env`. Never printed.
- Transport is `curl` (180 s timeout on API calls, 300 s on downloads). Python `urllib` is not used here.

## Models

| `model` | Mode in the manifest | Inputs |
|---|---|---|
| `bytedance/seedance2-0-fast-r2v` | `B` / `C` (**default**) | `reference_images: [url…]`, max **9** (the runner slices `refs[:9]`) |
| `bytedance/seedance2-0-fast-i2v` | `A` | `img_urls: [first(, last)]` — a **start frame**, not an identity ref |
| `bytedance/seedance2-0-fast-t2v` | `T` | prompt only, no refs (369 Studio Creator lane) |

Refs and frames are mutually exclusive by mode: in mode `A` the manifest's `refs` are ignored entirely.
**A previous clip's last frame belongs in a reference slot, never in `first`** — first-frame mode hard-cuts.

## Request body (exactly what `run_crun.py` sends)

```json
{ "model": "bytedance/seedance2-0-fast-r2v",
  "input": { "prompt": "<contents of docs/s7.txt>",
             "reference_images": ["https://…", "…"],
             "resolution": "480p", "aspect_ratio": "16:9",
             "duration": 10, "audio": true, "return_last_frame": true } }
```
Mode `A` swaps `reference_images` for `img_urls`; mode `T` has neither.

## `return_last_frame` — how the last frame actually comes back

`return_last_frame: true` is sent on **every** submit (r2v/i2v/t2v). There is **no named last-frame field**.
Crun appends the last frame as an **extra image entry in `result.media_urls`** — `media_urls[0]` is the mp4 and
the runner scans `media_urls[1:]` for the first `.png/.jpg/.jpeg/.webp` (typically `…_1.png`), downloading it to
`renders/cr_<id>_last.png`. That file is the continuity ref for the next clip; no ffmpeg frame extraction is
needed any more.

## Parameters and limits

- **refs ≤ 9** (r2v). Slots in practice: look portrait(s) / full character sheets · set or scene master · previous clip's last frame.
- **duration** clamped by the runner to **4–15 s**; 15 s is the house hard cap per clip.
- **resolution**: `480p` default (`$CRUN_RES`); higher is available but the house lane is 480p.
- **aspect_ratio**: per-item `ar`, `9:16` default in the runner; productions use `16:9` or `9:16`.
- **audio**: `true` by default — dialogue is generated natively in the clip, never overdubbed.
- Wall time ~5 min per clip.

## Cost

- **~88 cr ≈ $0.43 for a 10 s 480p clip**; **~132 cr ≈ $0.64 for 15 s** (≈ $0.043/s).
- `CREDIT_USD = 0.0048731` in `tools/ledger.py` — credits are the billed unit, USD is reporting only.
- Actual credits come back as `data.credits` and are written to `renders/cr_<id>.mp4.json` and the ledger.

## Ref hosting — litterbox vs uguu (RUNBOOK §N)

Local ref files are uploaded once and cached in `renders/crun_urls.json` keyed `rel:mtime:host`.
litterbox uploads **succeed**, then ByteDance fails to fetch them: `code 422: Failed to download media from the
provided URL`. Re-uploading to litterbox does not help — only changing host does.

```bash
CRUN_HOST=uguu python3 tools/run_crun.py projects/<proj> gen_s7.json
```
**Use `CRUN_HOST=uguu` by default on new projects.** With it set, the runner tries uguu.se first and falls back
to litterbox; unset, the order is reversed.

## Moderation — `451` on input AND on output (RUNBOOK §P)

Seedance rejects on **register, not subject**. Two real failures:
- `code 451 input` on romance wording ("camisole", "near-kiss") — the task is never created.
- `code 451 output` on an energetic dance shot — the task runs, then fails.

Fix both by describing the thing as what it is, with modest / high-neckline wardrobe wording and calmer motion
verbs. Do **not** remove the scene. §K governs how far an intimate beat may go at all.

## Delivery hazards (RUNBOOK §O, §S)

- **400 KB floor.** `CRUN_MIN_BYTES` defaults to **400000**; anything smaller is recorded as `truncated`, not
  success. The old 100 KB floor let a 196 KB file with no moov atom through as a finished clip.
- **CDN stall.** `static.mediaoss.bar` intermittently stalls a download at ~192 KB. `--http1.1` and `-C -` do not
  rescue it. The runner retries 3× then parks the partial; re-pull later from the media URL.
- **The sidecar is written before the download**, so `renders/cr_<id>.mp4.json` keeps the media URL even when the
  transfer dies. The `_last.png` usually lands fine, so **the chain survives a failed video download.**
- A `success` status with empty `media_urls` is a recorded failure, not an exception that kills the poll loop.
- **A FAILED id is skipped forever** — the failure handler leaves `tid` in `renders/crun_state.json` and the
  submit loop skips any id that has one. Resubmit with `--retry`/`--force <ids>`, which clears that state.

## Commands

```bash
python3 tools/run_crun.py projects/<proj> gen_s7.json --dry-run          # resolve prompts + refs, spend nothing
CRUN_HOST=uguu python3 tools/run_crun.py projects/<proj> gen_s7.json     # submit + poll + download (resumable)
python3 tools/run_crun.py projects/<proj> gen_s7.json --retry s7         # re-roll a FAILED/truncated id
python3 tools/ledger.py show|failed|chain|cost <proj>                    # state, retakes, chain readiness, spend
```
The `[ids…]` filter applies to the poll phase too, so a single-scene call no longer drags in every other
unfinished scene. The driver `tools/santan_run.py` runs scenes sequentially and injects the previous clip's last
frame as the final ref; ~4–5 clips fit in one 600 s Bash call and the runner is resumable, so just re-invoke.

## Known quality weaknesses

- **3–4 people talking in one frame** is ByteDance's own named weakness. Reblock to shot/reverse-shot: one
  identity to hold and one mouth to sync per generation. Inserts (hand, object) need no face and no lip-sync.
- **480p softness** — the lane is 480p, so assembled finals are soft. The Crun Media Enhancer on the **assembled
  final** is the candidate remedy (RUNBOOK §M) and is **not locked** — bench before using.
- **Strips clothing on intimate-register prompts, 3/3.** The full 3-panel character sheet as an r2v ref is the
  fix — costume held 4/4 (RUNBOOK §L). A single photo as the only ref gives a generic face; the sheet's outfit
  overrides the prompt's outfit.
- Invents background people when a body in frame is unattributed → CAST block is mandatory.
- Identity drifts whenever the prompt describes a face alongside an attached plate.
- Hindi dialogue needs whisper-medium verification on every clip, including no-line shots.

## When NOT to use this

- **Anything that must be sharp at 1080p+ per clip** — this is a 480p lane; do not try to fix that with a re-roll.
- **A crowded dialogue frame (3+ speaking).** Reblock into single-subject shots instead of paying for re-rolls.
- **Nudity or sexual content** — refused by §K on our side and by `451` on theirs; a rewrite will not buy it.
- **Anything already delivered as `truncated`** — that is a transfer problem, not a generation problem. Re-pull
  from the sidecar URL; do not pay for another render.
- **A shot whose prompt has not passed the PRE-SPEND gate** (`--dry-run` clean, chain not BLOCKED,
  PROMPT-STANDARD pre-flight complete). Submitting first and QC-ing after is what this lane punishes.

## Pointer
→ `knowledge/PROMPT-STANDARD.md` (prompt law) → `knowledge/RUNBOOK.md` §I §J §K §L §M §N §O §P §S
→ `.claude/agents/qc.md` (the gate) → `knowledge/vendors/atlas-gpt-image2.md` (the refs this lane eats)
