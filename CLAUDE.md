# studio369 — AI video production studio

Nipam's own stack: script → reference images → Seedance clips → QC → assembled final, as plain
Python + ffmpeg from `tools/`. The ported MiniMax Design architecture (media-agent →
router/planner/executor → `plan.py` / `gen.py` → canvas) is in
`knowledge/ARCHITECTURE-minimax-port.md` — **no production here has ever run through it.**

## 0. Session start

- Working language = the user's chat language (Hinglish for Nipam).
- Load the `task-observer` skill, then `stack-router`.
- Keys live in `~/.config/keys_crun.env` and `~/.config/keys_atlas.env` (plus `~/.config/keys.env`
  for `SUNOAPI_KEY` and `GLM_API_KEY`). Keys are **never printed**, never pasted into a web field.

## 1. LANES (live only)

| Modality | Lane id | Runner | Cost | Caps |
|---|---|---|---|---|
| Video | `seedance_fast_crun` | `tools/run_crun.py` | 88 cr ≈ $0.43 /10 s · 132 cr ≈ $0.64 /15 s | 480p, refs ≤9, 15 s cap |
| Image ₹0 | `nano_banana2` | `topview-unlimited` MCP (Nano Banana Pro) | ₹0 | 2K |
| Image paid | `atlas_gpt_image2` | `tools/run_atlas_img.py` | $0.004 t2i · $0.005 edit | refs allowed |
| Music | `suno` | `tools/suno.py` | plan | — |
| Post | — | `tools/post.py` | local ffmpeg | — |

**Image-lane rule: prefer the ₹0 topview lane; Atlas is the paid fallback when topview is
unavailable or the job needs edit-with-refs.** `flow-unlimited` is NOT MCP-connected (an open
Chrome window does not connect an MCP server); the `higgsfield-unlimited` entitlement was
inactive on 22 Sep 2026.

## 2. HARD RULES

1. The prompt standard is mandatory for every video prompt — `knowledge/PROMPT-STANDARD.md`;
   reference implementation `tools/santan_build2.py`.
2. QC before every rupee: every image checked against script, cards and sheets
   (`.claude/agents/qc.md`); images are fixed free, video never spends on an unverified frame.
3. Timing: 10 s = 3 beats (0–3.5 / 3.5–7 / 7–10), ~3–4 per 15 s; 15 s is the hard cap per clip.
4. Chaining: each clip's last frame is the next clip's continuity ref with its own narrow job;
   **reset at every location/time cut**; never retell the previous clip.
5. Never describe a face when a reference plate is attached — only "the exact person shown in
   @ImageN, face and hair unchanged"; text describing a face competes with the plate and loses.
6. Intimate content: embrace, jacket/strap slipping, silhouettes yes; nudity, exposed chest,
   sexual touching never. Moderation `451` fires on **input and output** — modest wording clears
   it.
7. Always `--dry-run` before spend (resolves prompts and refs, prints what is missing) and
   `--retry <ids>` for failures — a FAILED clip is otherwise skipped forever (its task id stays in
   `crun_state.json`).
8. Finals: 1080p lanczos, 25 fps, `loudnorm I=-16`, H.264 `-pix_fmt yuv420p -movflags +faststart`.

## 3. PIPELINE

1. **Script** → `projects/<slug>/docs/script.md` (scenes, shot ids, durations, dialogue).
2. **Sheets / cards** → topview MCP `generate_image`, or
   `python3 tools/run_atlas_img.py projects/<slug> docs/<slug>_jobs.json` → `refs/<id>.png`
3. **QC the refs** → dispatch the `qc` agent; sheet them side by side vs script + wardrobe.
4. **Prompts** → `python3 tools/santan_build2.py` → `docs/v_<id>.txt`, one per shot.
5. **Clips** → `python3 tools/run_crun.py projects/<slug> docs/shots.json --dry-run`, then the
   same without `--dry-run` → `renders/cr_<id>.mp4` + `renders/cr_<id>_last.png`.
6. **QC the clips** → `ffmpeg -i clip.mp4 -vf "fps=1,scale=180:-1,tile=8x1" qc/<id>_tile.jpg` +
   whisper; then `python3 tools/ledger.py show <slug>`.
7. **Assemble** → `python3 tools/post.py` (normalize 25 fps → concat →
   `loudnorm=I=-16:TP=-1.5:LRA=11` → srt) → `final/` + `docs/qc-report.md`.

## 4. LEDGER

**Ledger (built 23 Sep 2026, RUNBOOK §S) — use it, do not re-derive clip state by hand.**
`python3 tools/ledger.py cost|show|chain|failed <proj>` reads `renders.db`, the one index joining
clip id → task id → status → credits → chain ref → last-frame path. Before any spend run
`run_crun.py … --dry-run` (resolves prompts and refs, prints what is missing); to redo a failed
clip use `--retry <ids>` — a FAILED clip is otherwise skipped forever because its task id stays in
`crun_state.json`. Downloads under 400 KB are `truncated`, not success.

## 5. AGENTS

- `.claude/agents/qc.md` — **live.** The gate: images vs script/cards/sheets, clips vs tile +
  transcript, before and after spend.
- `.claude/agents/router.md` · `planner.md` · `executor.md` — intent routing, Stage Execution
  Plan authoring, stage execution. All three belong to the archived ported path, not live work.
- `.claude/skills/jev` — **live.** Typed text decisions (`tools/jev.py`): triage a QC failure,
  score a prompt against PROMPT-STANDARD before spend, classify a 451, rank a batch. Text only —
  never for anything visual. Batch every question about one state into ONE call.

## 6. WHERE THINGS ARE

```
CLAUDE.md         this file — the live studio rules
knowledge/        RUNBOOK · PROMPT-STANDARD · CHANGELOG · ARCHITECTURE-minimax-port
                  vendors/ · failures/ · templates/ · workflows/ · image-recipes/
tools/            run_crun · run_atlas_img · santan_build2 · santan_run · ledger · post
                  suno · qc_sheet · jev · bench_assemble · capabilities.json
tools/_disabled/  runners of disabled lanes — they never sit in tools/ looking runnable
projects/<slug>/  refs/ · docs/ · renders/ · final/
server/           369 Studio web app (Docker, Render)
renders.db        the clip ledger (gitignored, rebuildable)
```

- **PC master:** `C:\Users\admin\.hub-global\skills\Claude outputs\studio369`
  (device VM: `$HOME/mnt/Claude outputs/studio369`). **Cloud mirror:** `/home/claude/studio369`.
- PC → cloud with `device_stage_files`; cloud → PC with `zip -0` (+19 MB `split`) +
  `device_commit_files` — never commit raw mp4/jpg, the bytes get altered.

## 7. HOW TO CHANGE A RULE

Follow RUNBOOK §H: bump `knowledge/CHANGELOG.md` (new block on top) → `tools/capabilities.json`
(`_version` / `_rule` / `_drama_rule`) → this file → `.claude/agents/qc.md` → README.md →
project status doc, on cloud **and** PC. Nothing is "current" until `capabilities.json`,
`CLAUDE.md` and `CHANGELOG.md` all say so. When a lane is disabled its runner moves to
`tools/_disabled/` and the `capabilities.json` default is repointed in the same change.

## 8. WHAT IS OFF

- **viggle · protoface · vgenv · fal** — v7.4, 15 Sep 2026 → `knowledge/CHANGELOG.md`,
  `knowledge/vendors/protoface-vgenv.md`.
- **Flow video** — never used → `knowledge/CHANGELOG.md`.
- **flow-unlimited images** — not connected → RUNBOOK §Q.
- **`gen.py` / `plan.py` canvas path** — archived, never ran →
  `knowledge/ARCHITECTURE-minimax-port.md`.

## 369 Studio deploy

**369 Studio deploy (verified 23 Sep 2026):** repo `369network/369studio` branch `main`; Render service
`srv-dalu0idbedkc738abl3g`; live at **https://three69studio.onrender.com**. Auto-deploy needs the **Render GitHub
App installed on the repo** — the UI saying "On Commit" is not enough (RUNBOOK §R). `VOICE_API_KEY`,
`SUPABASE_SERVICE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` are still unset in Render; Nipam adds keys
himself — never paste a key into a web field. Starter plan is 512 MB and has already OOM'd once.

## Jev / TypeSafe AI

**Jev / TypeSafe AI — evaluated 23 Sep 2026, viable for text decisions, NOT for anything visual.** Typed
text-only decisions (choice/score/noul), **$0.042/M input, output free**, ~0.24 s. Open self-serve signup since
20 Sep ("available to everyone, no waitlist") at console.typesafe.ai.
**Volume is NOT a constraint** — official limits are **250k tokens/sec and 1,200 requests per MINUTE** (an
earlier note in this file said "per month"; that was wrong and is corrected here). Our entire plausible usage
costs **$1–5/month**. Batch many questions into one call — TypeSafe's own cookbook measures 13 questions batched
as 12.2x cheaper and 10x faster with identical answers.
**The real limits:** (a) **no vision — it cannot do frame QC**, images/audio/video "not supported (yet)";
(b) documented weaknesses in counting, dates, arithmetic, indirection and large noisy state; (c) on TypeSafe's
OWN published evals Jev is mid-pack on accuracy (67.8%, tied with sonnet 5, ~6 pts below sol/opus 5) — the win
is cost and latency, not quality; (d) "zero hallucinations" means zero out-of-schema outputs, which they state
is a non-empirical type-safety claim, not correctness; (e) no SLA, prepaid credits expire in 12 months, rate
limits "can change without notice" with immediate suspension on breach.
**Never use jevai.org** — unofficial proxy, anonymous domain registered the day after launch, its key does not
work on the real API and its own quota dies after ~5 calls. Official surfaces: docs.typesafe.ai direct, or
OpenRouter (identical $0.042/M, full Decisions API, 5.5% top-up fee) as fallback.
**Still do the ledger first** (clip id → task id → URL → status → last-frame path in JSONL/SQLite) — it needs no
Jev at all. Full evaluation: project doc `claude/jev-typesafe-evaluation.md`.
**Wired 23 Sep 2026:** `tools/jev.py` + the `jev` skill (`.claude/skills/jev`), with three ready
packs — `prompt-preflight` (the PROMPT-STANDARD checklist as 8 typed checks, ~$0.00005 a shot),
`qc-triage`, `moderation-451`. The client validates question shapes locally before spending a
call and returns a diagnosed error. **Two routes, same model and wire format** — `OPENROUTER_API_KEY`
in `~/.config/keys_openrouter.env` (preferred; returns a real per-call cost) or `JEV_API_KEY` in
`~/.config/keys_jev.env`; `--via` forces one. The jevai.org key still on disk 401s on both and
must be discarded.
