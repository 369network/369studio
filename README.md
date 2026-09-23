# studio369 — Nipam's own MiniMax Design · **v7.5 (15 Sep 2026)**

One prompt in → brief → plan → ₹0 images (cards, scene master, keyframes) → QC → viggle/protoface H3 clips → QC → post → final. MiniMax Design v3.0.14 architecture (media-agent + router/planner/executor + Stage Execution Plan + workflows + 115 skills) running on Claude Code with Nipam's own lanes.

Proof: Hisaab EP1–EP4 (Hindi drama, 80–100 s each), Overnight-17 US benchmark (17 categories, 20/20 tests agency-ready, avg 8.4/10). Full history: `knowledge/CHANGELOG.md`. Day-to-day commands: `knowledge/RUNBOOK.md`.

## Hard rules (never break)
1. **Images (v7.8, 23 Sep 2026)** — prefer the ₹0 `topview-unlimited` MCP (Nano Banana Pro). Atlas Cloud GPT Image 2 (`tools/run_atlas_img.py`; t2i $0.004, edit-with-refs $0.005) is the paid fallback and is required for edit-with-refs. `flow-unlimited` is not MCP-connected. Identity = edit from the real photo / master portrait.
2. **QC gate before every rupee** — every image checked against script, location card, prop card, wardrobe card, scene master and character sheet (`.claude/agents/qc.md`); every clip checked with a 1 fps tile + whisper (no-line shots too). Fix images for free, never spend video on an unverified frame.
3. **Video lane (Nipam, v7.4)** — EVERY shot on Crun Seedance 2.0 FAST (`tools/run_crun.py`, 480p, $0.043/s). viggle / protoface / vgenv / fal / Atlas disabled — re-enable only on Nipam's word. TopView = images only. Never Flow video.
4. **One Flow queue at a time; runners launch from Windows** (Desktop Commander `Start-Process`) — device-VM background processes die.

## Pipeline v7.2 (drama / any multi-shot job)
```
script.md ──► assets (Atlas GPT Image 2): casting portrait (edit from photo) · character sheet · location card (4-panel) · prop card · WARDROBE card
          ──► scene master (one approved wide per scene, + depth sentence)      ─┐ all ₹0, QC each
          ──► 3-panel shot masters (Mode A) + keyframes (Mode B), each ref = scene master ─┘
          ──► Crun Seedance FAST, all shots (tools/run_crun.py, PC or cloud) → post upscale 1080p
          ──► per-clip QC: tile + whisper  ──► re-roll on Crun with a fixed prompt for fails only
          ──► assemble (normalize 25 fps → concat → loudnorm −16 LUFS → srt) ──► qc-report.md ──► final/
```
Guards: Mode A (first/last frame) only when master p1 and p3 share composition **and** cast, else Mode B off the fullest panel. No-line shots: `【对白】无` + lips closed, no voice-signature block, never "heavy breathing / throat sounds". Every keyframe carries the COSTUME LOCK line. Every clip carries the identical 【角色声音签名】 block (animation too). Continuation shots: previous clip's last frame as first_frame (chain ≤3), previous keyframe as fallback ref. Storyboard = planning/QC board only; storyboard-ref-to-video = montage/trailer lane only.

## Lanes & cost (locked)
| Need | Lane | Cost |
|---|---|---|
| Images, characters, cards, keyframes | `topview-unlimited` MCP (Nano Banana Pro) | ₹0 |
| Images — edit-with-refs / topview down | `atlas_gpt_image2` (`tools/run_atlas_img.py`) | $0.004–0.005 |
| **Every video shot** (drama, ad, montage, Mode A/B/C) | **seedance_fast_crun** (crun.ai `seedance2-0-fast-r2v`, 480p, ≤9 refs) | $0.043/s (15 s = 132 cr = $0.64) |
| Disabled (runners in `tools/_disabled/`) | viggle H3 · protoface · vgenv · fal · Flow video · Atlas **video** | — |
| Music / song | Suno via `tools/gen.py music` | plan |
| Dubbing | regenerate the shot with the target language (lips match) | $0.01/s |

Sellable menu (v7.4 cash cost): 15 s product ad $0.64 · 30 s TVC $1.28 · 20 s UGC $0.86 · 90 s drama episode ≈ $4.50 incl. retakes · 3 min short ≈ $10 · 60 s trailer $2.60 · 30 s MV $1.28 + Suno · dub $0.043/s. Per-category recipes: `tools/capabilities.json → lanes.video._category_lanes`.

## Layout
```
CLAUDE.md                     orchestrator (media-agent) + contracts; start every session with task-observer → stack-router
.claude/agents/               router · planner · executor · qc (the gate)
.claude/skills/               stack-router (lanes, H3 grammar) · drama-series · ad-tvc · mv · promo-video · presets · nano-banana-prompt-finder (40,986 prompts, offline search) · seedance2-prompting (Seedance structure guide) · minimax/<115>
tools/plan.py                 Stage Execution Plan API
tools/gen.py                  generation dispatcher (video lanes protoface_h3 / vgenv_h3 / fal; music Suno; image = unlimited MCPs)
tools/run_atlas_img.py        Atlas GPT Image 2 runner (jobs.json → refs/<id>.png; edit with refs) — THE image runner
tools/run_crun.py             Crun Seedance FAST runner (manifest → renders/cr_<id>.mp4, refs auto-hosted, resumable) — THE video runner
tools/run_viggle.py           viggle H3 runner (disabled lane, kept)
tools/run_clips2.py           protoface retakes from the same manifest (mode A first/last, mode B refs)
tools/run_flow_kf2.py         Flow keyframe batches with paste-fail retry (one queue!)
tools/bench_assemble.py       assemble <test> [ar] [id=path overrides] → final/<test>.mp4 + 720p
projects/bench-intimate/docs/crunfast.py  Crun Seedance-FAST backup runner (submit|poll) · prov.py = Atlas #2
tools/bench_qc.py · post.py   tile sheets · ffmpeg post (concat/mix/subs/loudnorm/textfix/transcribe)
tools/capabilities.json       lanes, prices, _rule, _drama_rule, _category_lanes  (_version 7.5)
knowledge/CHANGELOG.md        rule-set history v4 → v7.5
knowledge/RUNBOOK.md          copy-paste commands for an episode / ad / benchmark
knowledge/vendors/            protoface-vgenv.md (H3 API + viggle facts), unlimited-mcps-v4.md, MiniMax vendor cards
projects/<slug>/              brief.md · docs/(script, shots.json, v_*.txt, subs.txt, qc-report.md) · refs/(cards, v/, v2/) · renders/ · final/
hooks/anti_loop.py            LoopGuard
```

## Machines
- **PC** (`C:\Users\admin\.hub-global\skills\Claude outputs\studio369`) = master copy. Flow MCP venv `C:\Users\admin\flow-unlimited-mcp\.venv`. viggle key `.config/keys_viggle.env` (PC only — Cloudflare blocks the cloud). Runners launched via Desktop Commander `Start-Process` with `$env:VIGGLE_QUALITY="high"`.
- **Cloud container** = protoface/vgenv/fal/Suno calls (`~/.config/keys.env`), whisper QC (faster-whisper medium), report/artifact building. Move media PC→cloud with device_stage_files; cloud→PC with zip -0 (+19 MB split) + device_commit_files (raw binaries get altered).

## Mode C (multi-shot ref-to-video) — drama default for dialogue scenes
One ≤15 s clip, ≤3 internal shots, refs (viggle cap 4) = look portrait A + look portrait B + set + last frame of previous clip; no keyframes; lines verbatim per shot. Look portrait = character in THAT scene's costume (Flow chip + wardrobe card, ₹0). Chain ≤3 clips then restart from the scene master. 5–9 refs → protoface_h3. Proof: REDLINE sc.3 = 2 clips $0.30 vs 6 clips + 6 keyframes. Deliver viggle clips as H.264 (source is HEVC). Full rule: RUNBOOK §J.

## Length rule
Every H3 lane (viggle, protoface, vgenv, fal, Seedance FAST) caps at **15 s per clip**. A "30 s single take" is always a 2×15 continuation chain (last frame → first frame) — viggle only; Seedance mini cannot chain (frames XOR refs).

## Known traps (all handled in tooling)
Flow: first job paste-fail → retry · auto-download can save the wrong tile → always download from the signed `images[0].url` · character chip "No project asset matches" after ~60 jobs → retry round · never two Flow scripts at once · prompt box leaks into next job. viggle: reference mode needs `duration_s ≥ 5`; 1080p same price. Windows: `set X=.. &&` adds a trailing space → use `$env:`. Mode A with mismatched panels hard-cuts on every lane.
