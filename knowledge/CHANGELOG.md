## v7.8 — 23 Sep 2026 — system audit: every remaining problem closed

Follows the four-part audit (project doc `claude/system-audit-2026-09-23.md`). Steps 1 and 2 were
the security patches and the ledger; this block is everything that was left.

**Rule layer re-joined to the execution layer (was B7).**
- `CLAUDE.md` 53 KB → 9 KB, current-only. The 41 KB MiniMax port moved verbatim to
  `knowledge/ARCHITECTURE-minimax-port.md`, headed as archived — no production ever ran it.
- Dropped as false: "Do not use shell, Python, ffprobe, PIL, or curl for media work" (that is the
  entire pipeline); "Default direct-video selection is H3 (fal lane by default)"; the v6 fallback
  chain; "finals 1080p viggle"; the FAL/REPLICATE/POLLO/PROTOFACE/VGENV key list; "images = Atlas
  only, unlimited MCPs disabled".
- `tools/capabilities.json` v7.8: video default `protoface_h3` → **`seedance_fast_crun`**; image
  default `higgsfield_unlimited_mcp` → **`topview_unlimited_mcp`** with `atlas_gpt_image2` as the
  declared fallback; 15 dead video lanes flagged `enabled: false` with the date they were retired.
- `tools/gen.py`: new `assert_lane()` guard refuses any lane marked disabled — nothing checked
  this before, so a call without `--lane` aimed at a banned paid vendor. Fixed the one-line
  `if …: raise …; prompt=…; out=…` that put the assignments inside the if-body and made
  `gen.py image` raise `NameError` on every allowed lane.
- **One image law, in one place.** `stack-router/SKILL.md` ("images are NEVER paid"), `README.md`
  ("EVERY image on Atlas") and RUNBOOK §Q all said different things; all now say: prefer the ₹0
  topview lane, Atlas is the paid fallback for edit-with-refs.
- RUNBOOK §I's "never costume-critical drama, never chains, never Hindi dialogue" marked
  SUPERSEDED — santan is all three, and v7.4 overrode it 8 days earlier.

**QC reconnected (was B8).**
- `.claude/agents/qc.md` rewritten against the real layout (`refs/`, `docs/s*.txt`,
  `scenes_A.json` — it was reading `assets/characters/` and `docs/storyboard.md`, neither of which
  exists) and the real failure modes: costume strip, identity drift, invented background people,
  floating cloth, 451 on input AND output, truncated download, cropped sheet face, black tail,
  480p softness. Adds a **pre-spend** gate (prompt-standard checklist + `--dry-run` +
  `ledger.py chain`) — the cheapest place to catch anything.
- `tools/bench_qc.py` retired: it globbed `vg*_` / `c2_` and was structurally blind to every
  `cr_*.mp4` since 15 Sep. Replaced by **`tools/qc_sheet.py`** — any project, any lane, tile
  sheets plus hard checks (size, ffprobe readability, audio track, black tail, missing
  last-frame) and a non-zero exit so it can gate a script.
- First two vendor cards for the lanes we actually use: `knowledge/vendors/crun-seedance.md` and
  `knowledge/vendors/atlas-gpt-image2.md`. The folder had 16 cards and none for Crun or Atlas.

**Platform (was B5 / B11).**
- Whisper is now one cached instance behind `QC_WHISPER` (default model `tiny`), not a fresh
  400–500 MB `small` model per job inside a 512 MB web process — that was the OOM loop.
- `MAX_CONCURRENT_JOBS` semaphore (default 2); nothing capped in-flight renders before.
- **Reaper**: on boot every row still `running` is orphaned by definition — failed and refunded;
  a background sweep does the same for anything past `JOB_MAX_AGE`. Restarts used to leave rows
  stuck at `running` forever with the credits already spent.
- Stripe: `/api/stripe/checkout` now authenticates the caller instead of trusting `user_id` from
  the request body; webhook is idempotent on `event.id`; a new subscription no longer grants
  month one twice (`checkout.session.completed` defers to `invoice.paid`). A startup warning
  fires while `PLANS` still holds placeholder price ids.
- **Character library — the audit's claim here was wrong, twice.** The first pass reported
  `server/static/library/` as missing; the second said it existed on the PC but was never
  committed. Neither is true: **all 150 files (75 faces + 74 voice samples + `library.json`) have
  been tracked in the repo since before this audit**, so Render has always served them. What was
  actually missing was the folder in the *cloud working copy*, which is what produced the 404s
  observed locally. `.gitignore` gains `!server/static/library/*.mp3` anyway — not to fix a break,
  but so a NEW voice sample dropped into that folder is not silently skipped by the blanket
  `*.mp3` rule (which never affected the already-tracked files).
  The voice endpoint does now say in its response when it fell back to the stock voice and why —
  that part stands.

**Keys out of `ps` (was B11).** `run_crun.py`, `run_atlas_img.py` and `gen.py` passed the API key
as `-H "Authorization: …"` in argv, readable by any local process. All three now write a 0600
`curl -K` config removed at exit. Verified equivalent against httpbin.

**LoopGuard (was B11).** `hooks/anti_loop.py` exempts the resumable runners — RUNBOOK §O's
documented recovery is "just re-invoke", which the guard was blocking on the third try. History
parsing is defensive (a torn line used to crash the hook instead of allowing the call) and writes
are atomic. `.claude/settings.json` matcher now includes `Task` as well as `Agent` — the
sub-agent tool is `Task`, so sub-agent dispatch was never guarded at all.

**Retired to `tools/_disabled/`:** `santan_build.py`, `run_clips.py`, `run_v4_clips.py`,
`run_flow_kf2.py`, `bench_qc.py`.

# v7.7 — 23 Sep 2026 — Prompt standard mandatory

- `knowledge/PROMPT-STANDARD.md` added and referenced from CLAUDE.md. Every video prompt now written to it.
  Load the `seedance-film-director` skill before authoring shots.
- Six locks: no face description with a plate attached; never the word "cinematic"; one job + do-not-copy clause
  per ref; CAST block naming every body in frame; mandatory ENDING STATE; AUDIO positive-first with
  background-voice exclusion.
- Validated by rebuilding santan s1-s5 (v1 -> v2): the rendered/CGI look is gone and identity holds.
- `tools/run_crun.py`: always `return_last_frame: true` + auto-saves `cr_<id>_last.png`; `CRUN_HOST=uguu`
  host switch (litterbox 422s on ByteDance fetch); <100 KB output treated as missing.
- `tools/santan_build2.py` + `tools/santan_run.py` are the reference builder/driver for chained productions.
- Jev / TypeSafe AI evaluated. **Correction (same day): the rate limit is 1,200 requests per MINUTE, not per
  month** — an earlier reading of the models table was wrong, and the "too little volume to be usable" conclusion
  built on it was wrong too. Volume and cost are non-issues ($1-5/mo for our usage). The real blockers are no
  vision (cannot do frame QC), mid-pack accuracy on their own evals, and no SLA. Never use jevai.org.
  Ledger still comes first. See project doc `claude/jev-typesafe-evaluation.md`.

# studio369 rule-set changelog

**Current: v7.6 (17 Sep 2026) — lanes unchanged (video = Crun Seedance 2.0 FAST, images = Atlas GPT Image 2); adds the Atlas 3-panel character-sheet template as the identity anchor + Crun Media Enhancer as the finishing/upscale option for 480p softness.** Newer entries first.

## v7.6 — 17 Sep 2026 (Atlas 3-panel sheet template + Crun skills review)
- **Character-sheet template locked (Atlas GPT Image 2, t2i).** One horizontal frame, 3 equal panels: LEFT = full-body FRONT with no head/neck/hair (invisible-body, hollow neckline — pure wardrobe view), CENTER = full-body REAR head-attached, RIGHT = tight chest-up identity close-up; 18% grey seamless, flat shadowless catalogue light, 50mm, "photographed not generated". Atlas nails the invisible-body panel cleanly (better than higgsfield for this catalogue-flat sheet). Made cs_vivek + cs_suzi, installed as `refs/{vivek,suzi}_fullsheet(_s).jpg` (old cast backed up `*.pre_csheet.bak.jpg`). Template text saved: `projects/afterhours/docs/csheet_vivek.txt` / `csheet_suzi.txt`, manifest `docs/csheet.json`.
- **These full sheets fix the two big Seedance problems** when used as r2v refs: costume held 4/4 (no shirt→tank strip) and identity stable across the chain. AFTER HOURS v6 (Ring, new cast, 60 s, 4×$0.64=$2.57): sd-01..04 all PASS, dialogue clean (put a one-word line in shot 1, later shots wordless, to avoid repetition).
- **Upload reliability:** litterbox can 502 on ByteDance's fetch even after a successful upload → seed ALL refs (sheets + last frames) to uguu.se directly and cache them; and clear the `renders/crun_state.json` entry for a failed id before re-submitting (runner skips resubmit while a `tid` is present).
- **Crun Agent Skills reviewed (crun.ai/skills):** candidate to test = **Crun Media Enhancer** (4K image super-res + video frame-rate interpolation) as the FINISHING lane for our 480p Seedance softness — upscale/interp the assembled final instead of changing the video lane. Also noted: native Character Reference Sheet, Action & Camera Director (camera/VFX prompt enhancement), AI Special Effect & Video Templates (Kling/Vidu/ByteDance presets). Base 3 (Account Credits / Model Router / Task Runner) already covered by our run_crun.py + capabilities.json — not needed. None locked yet; Media Enhancer to be benched on a v6 clip first.

## v7.5 — 15 Sep 2026 (Nipam: "only Atlas GPT Image 2 for images, Crun for video — dono lock")
- **Images:** Atlas Cloud GPT Image 2 is the ONLY image lane (`atlas_gpt_image2`, `tools/run_atlas_img.py`; t2i $0.004, edit $0.005 with `images[]` refs). Flow / Higgsfield / TopView disabled (re-enable only on his word). Test bench-img: look portrait from Vivek's real photo (identity + new outfit ✓), Suzi sheet → new outfit ✓, garage 4-panel ✓, car 3-view with "369" text ✓, wardrobe flat-lay ✓ — 5/5, $0.022, ~60 s parallel, no browser. Replaces the Flow character-chip identity mechanism: identity now = edit-from-portrait.
- **Video:** Crun Seedance 2.0 FAST stays the only video lane (v7.4).
- AFTER HOURS v2 (60 s): 4 clips, $2.57; "Now." misheard as "No" → line replaced ("Turn it off."); RUNBOOK §K limits kept.
- Cost per 90 s episode now ≈ $4.50 video + ≈ $0.20 images.

## v7.4 — 15 Sep 2026 (Nipam: "sab video ke liye Crun Seedance 2.0 FAST")
- **Decision (Nipam):** Crun Seedance 2.0 FAST (`bytedance/seedance2-0-fast-r2v`, 480p, 132 cr = $0.64 per 15 s) is the ONLY video lane for every shot — drama, ads, montage. viggle / protoface / vgenv / fal / Atlas disabled in capabilities (kept for emergencies, re-enable only on his word). Reason: cinematic quality (motion 9/10, staging, skin) — "mehnga hai par quality hai".
- Runner: `tools/run_crun.py <proj> <manifest> [ids]` — same manifest as run_viggle; refs auto-hosted on litterbox (cached), Mode B/C → `reference_images` (≤9), Mode A → `fast-i2v img_urls`; outputs `renders/cr_<id>.mp4` + credits json; resumable.
- Known risks carried into production (from the 15 Sep benches): costume drift on physical/intimate prompts (3/3), 480p native (post upscale), Hindi dialogue 3/7 verbatim, no first/last + refs in one call, media deleted after 14 days (download immediately). QC gate unchanged.
- Cost reality: 90 s episode ≈ $3.90 + retakes (was $0.90–1.20 on viggle); 3 min short ≈ $9.60.
- **AFTER HOURS (client via Vivek, 15 Sep):** first paid job on v7.4 — 30 s, 9:16, EN, 2 × 15 s Mode C on Crun FAST, $2.57 incl. 2 retakes. Content rules written into the system: no nudity, no sexual touching; a real person's face never appears in undress/body beats (AI/body-double framing: back of head, silhouette, hands); sensual level = kiss, jacket/strap, hands on waist/back. Lesson: on any "intimate" prompt Seedance turns the man's shirt into a tank top **3/3 times, in r2v with photo ref AND in i2v from an exact start frame** — plan body beats as silhouette / hands-only, or accept the undershirt as diegetic. Retake ladder that worked: hard costume negative → hidden face ✓; i2v start frame → continuity ✓ but not clothing.
- Mode C on Seedance: refs up to 9 → look portraits + sheets + set + last frame all fit; chain via last-frame *reference* (R2V keeps identity).

## v7.3 — 15 Sep 2026 (Seedance FAST + Mode C multi-shot)
- Provider test (bench-intimate, same 15 s 3-shot prompt, refs = photo + character sheet): viggle high 1080p $0.15 · Crun Seedance mini 480p $0.21 · Crun Seedance FAST 480p $0.64 (132.17 cr) · **Atlas Seedance 2.0 FAST 480p $0.41** (167 s). FAST = same model on both, Atlas 36% cheaper + 2× faster. Seedance mini retired (FAST clearly sharper). apiyi key: no Seedance group (293 models, none seedance) — unusable. Seedance 2.5 FAST does not exist; 2.5 = $0.134/s (30 s native) — only for a true 30 s single take.
- Lane: `seedance_fast_crun` = Seedance backup #1 (Nipam's pick — same model/quality as Atlas; Crun account preferred), `seedance_fast_atlas` = #2 (cheaper, faster). Montage / hero-motion / single ≤15 s only. Seedance strips clothing on intimate prompts even with "clothes stay on" (3/3 Seedance runs) → never costume-critical drama. viggle high stays default (identity best, prompt obedience best, 1080p, cheapest).
- **Mode C = drama DEFAULT for dialogue scenes** (REDLINE sc.3 proof: 2 clips $0.30, 0 keyframes, 4/4 lines, continuity via last-frame ref vs 6 clips + 6 keyframes + 1 retake). Ref slots (viggle cap 4, docs-verified): look A + look B + set + last frame; look portrait = character in the scene's costume (Flow chip + wardrobe card); chain ≤3 clips; 5–9 refs → protoface. Details RUNBOOK §J.
- **Mode C (ref-to-video multi-shot)**: one ≤15 s clip with ≤3 internal shots, refs = portrait/photo + character sheet (+ scene master), NO keyframe, dialogue verbatim per shot. Proven on viggle 1080p: 3 shots on cue, 4/4 lines, identity + sheet outfit held. Use for same-room / same-cast dialogue beats (≈ $0.15 for 3 shots vs 3 × Mode B). Chain via ffmpeg last frame → next clip's last ref. Not for >2 characters, location change, or >3 beats.
- Delivery: viggle mp4 is HEVC — always H.264 re-encode (`-c:v libx264 -pix_fmt yuv420p -movflags +faststart`) before sending to chat/client.
- REDLINE lesson: Mode A prompt must never carry the 3-panel image-prompt text; a prop/vehicle that "arrives" mid-shot needs Mode B + its prop card as a ref.

## v7.2 — 15 Sep 2026 (Seedance 2.0 mini via reapi.ai tested)
- New lane `seedance_mini_reapi` (reapi.ai, $1 = 1000 cr): 480p $0.017/s, 720p $0.036/s, 4–15 s, 16:9/9:16, `reference_image_urls` ≤9 XOR `first_frame_url`/`last_frame_url`, `reference_video_urls` ≤3, `generate_audio`, public URLs only (base64 rejected), max 10 tasks in flight, ~2 min/clip. Key `~/.config/keys_reapi.env` (cloud); refs hosted on litterbox (72 h) for the API.
- Tests: EP4 full (15 shots): identity 15/15, 0 cuts, Hindi lines 3/7 (viggle 7/7), stray speech 4/8 silent shots, ≈ $1.50 vs viggle $0.94. Race 12 s: beat sheet 6/6 both; viggle sharper + cheaper. Ritual 30 s (2×15 chain): viggle I2V chain keeps identity; Seedance I2V chain drifts face (frames XOR refs), R2V chain keeps face but resets continuity.
- Provider: **Crun** (`seedance2-0-mini-r2v`, 206 cr = $1, $0.0142/s 480p, unlimited concurrency) replaces reAPI as the Seedance backup lane — same model/quality, 15% cheaper. Crun `i2v` = start-frame mode, not references.
- Skill added: `.claude/skills/nano-banana-prompt-finder` (Nipam-supplied plugin; 40,986 youmind prompts, 11 models, offline search) — prompt lookup before ₹0 image jobs and montage/ad video prompts.
- Skill added: `.claude/skills/seedance2-prompting` (Nipam-supplied; YouMind corpus 6,278 prompts, CC BY 4.0) — owns Seedance-lane prompts, vocabulary bank for all lanes.
- Identity on Seedance mini: portrait + character sheet as 2 refs (1 photo → generic face); sheet outfit overrides prompt outfit.
- RULES: (1) viggle high stays default for every lane. (2) Every H3 lane caps at 15 s — "30 s single take" = 2×15 continuation chain, **viggle only**. (3) Seedance mini = single ≤15 s no-dialogue clips only (backup / 480p drafts); never Hindi dialogue, never chains. (4) Never say "pure 30 s" is possible on H3.

## v7.1 — 15 Sep 2026 (EP4 «Papa» + t14b/t12b re-runs)
- t14b: wardrobe card + scene master + COSTUME LOCK → dress identical 6/6 (v7 proven). t12b: identical voice-signature block + physics line for animation.
- EP4 «Papa» v1 delivered on v7 (15 shots, 95 s, viggle high 1080p, 7/7 Hindi lines, ≈ $1.17 + 24 cr).
- RULE: Mode A (first/last frame) only when master panels 1 and 3 share composition AND cast; otherwise Mode B off the panel that shows everyone (002-01 cut on viggle AND protoface — keyframe fault, not lane).
- RULE: no-line shots → remove every speaker's voice-signature line, write 【对白】无 + "lips closed, no whisper, no throat sounds"; never write "heavy breathing / throat sounds" (models turn it into mumbling). Whisper QC must run on no-line shots too (3/15 EP4 shots had stray speech).
- Runners on the PC launch via Desktop Commander `Start-Process` (device VM has no powershell.exe); `bench_assemble.py <test> [ar] [id=path]` overrides for retakes.

## v7 — 15 Sep 2026 (Overnight-17 US benchmark)
- 17 categories tested in one night with US cast/brands (invented), English native H3 audio: e-com ×4, TVC, action, UGC, 2-speaker, emotion/night, crowd, chain, elderly/kid, costume swap, trailer, animation, MV, EN vertical drama, dubbing EN/ES, audio, resolution. Results in projects/bench/docs/scorecard.json + report artifact.
- New rules: per-category lanes in capabilities `_category_lanes`; COSTUME LOCK / wardrobe card mandatory (t14 fail); ar per manifest item; 1080p viggle default for finals; dubbing = regenerate with language; two-speaker shots allowed; action shots single-location.
- Tooling: tools/bench_assemble.py, tools/bench_qc.py, docs/sync_kf.py pattern (download keyframes from the signed URL in results, never trust the auto-download file), Flow character chip failures after ~60 jobs → retry round; run_flow_kf2 + run_viggle resumable.
- English dialogue accuracy: 30/30 lines verbatim on viggle high (Hindi was 7/9) → for EN drama no protoface retakes were needed.
## v6 — 14 Sep 2026 (night)
- Clip lane: **viggle high first for every drama shot** (PC runner `tools/run_viggle.py`, parallel, ref-mode ≥5 s) → per-clip QC (tile + whisper-medium Hindi) → only failed shots on protoface (`tools/run_clips2.py … <ids>`) → assemble. EP3 3-way proof: viggle high 16/16 identity, 0 cuts, 7/9 lines; ≈ $0.85/episode vs ≈320 cr.
- Video cost order (Nipam): viggle high / protoface → vgenv (drafts) → fal turbo → fal 2K. TopView = images only. Never Flow video.
- Scene master per scene (approved wide → reference for every closer shot + depth sentence). Prop continuity cards (attach by Flow tile title). Continuation-frame fallback. Storyboard = planning/QC board; storyboard-ref-to-video = montage/ad lane only (54 cr/15 s PASS).
- QC gates added: geography/depth ("what is behind whom"), prop-vs-card, v6 viggle→protoface gate, continuation-chain sharpness.
- Runners: `run_flow_kf2.py` (paste-fail retry), `run_viggle.py` (resumable, per-quality state).
- Known bugs: Flow auto-download can save the wrong tile (re-fetch by media_id); never two Flow scripts at once; prompt-box leak into next job; device_commit alters binaries (zip -0 + split); Windows `set X=.. &&` trailing space; device-VM background procs die with the call.

## v5.x — 14 Sep 2026 (day)
- Flow pipeline: master portrait → Flow character → location cards → 3-panel masters → protoface modes A/B → per-clip QC. EP1 v5, EP2 v2 delivered.

## v4 — 14 Sep 2026 (morning)
- protoface_h3 chosen over vgenv (3/3 vs 0/4). Character bible template. EP1 v4.

