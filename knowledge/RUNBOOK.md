# studio369 RUNBOOK v7.6 — video = Crun Seedance FAST · images = Atlas GPT Image 2 — copy-paste commands

PC root: `C:\Users\admin\.hub-global\skills\Claude outputs\studio369` (device VM: `$HOME/mnt/Claude outputs/studio369`). Cloud root: `/home/claude/studio369`.

## A. Drama episode (Hindi, 9:16, ~90 s) — reference: projects/hisaab-ep04
1. **Script** → `projects/<ep>/docs/script.md` (scenes, shots 001-01…, dur 4–8 s, dlg lines, hook last). Subs → `docs/subs.txt` (`id | line`).
2. **Assets jobs (v7.5)** → `docs/<ep>_jobs.json` for `tools/run_atlas_img.py`: `{id, prompt, refs:[local paths] (edit) | none (t2i), size}`. One job each: casting portrait (edit from the real photo or master portrait), character sheet (edit from the portrait: front/side/back), location card (4-panel, t2i), prop cards, **wardrobe card per character**, look portrait per character per scene (edit from portrait + wardrobe card). `python3 tools/run_atlas_img.py projects/<ep> docs/<ep>_jobs.json` (cloud or PC, ~60 s, parallel) → `refs/<id>.png`.
3. **QC assets** (qc agent): sheet all refs side by side; check against script + wardrobe. Fix for free.
4. **Scene master + keyframes** → `docs/<ep>_kf_jobs.json`: first job `..._sm_<scene>` (16:9, character chips + location card ref), every other job `reference_images=[refs/<ep>_sm_<scene>.jpg]` + chips + COSTUME LOCK line. Masters (Mode A) = 3-panel 16:9 `m_<shot>`, keyframes (Mode B) = 9:16 `k_<shot>`. Run `<ep>_run.py kf`.
5. **QC keyframes**: identity, costume, room, props, geography (who is behind whom). Then build video refs: `refs/v/char_<name>.jpg` (master portrait), `refs/v/set_<scene>.jpg` (scene master), `refs/v2/k_*.jpg`, panel crops `m_<shot>_p1/p2/p3.jpg` (thirds). **Mode A guard**: use A only if p1 and p3 share framing + cast, else Mode B off p3.
6. **Mode split**: dialogue scenes → Mode C (§J, default); establishers / action / 3+ cast / prop arrival → Mode B keyframes below.
7. **shots.json** items: `{id, mode A|B, dur, prompt docs/v_<id>.txt, refs [char, set, keyframe] | first/last, dlg, lane "viggle1080", ar "9:16"}`. Prompt template = `docs/v_002-05.txt` (Chinese H3 grammar: 连续单镜头 · @Image roles · 环境光影 · 空间基准 · 角色声音签名 identical block · 画面演进 with verbatim line · 声音设计 · 画面风格). No-line shots: `【对白】无` + lips closed, NO voice-signature block.
7. **viggle high** (PC): `$env:VIGGLE_QUALITY="high"; Start-Process python -ArgumentList "tools\run_viggle.py","projects\<ep>","docs\shots.json" -WorkingDirectory "<root>" -RedirectStandardOutput ...\renders\vg.log -WindowStyle Hidden` → `renders/vghigh_<id>.mp4` (~10 min for 15 shots).
8. **Clip QC**: tiles `ffmpeg -i clip -vf "fps=1,scale=180:-1,tile=8x1" qc/<id>_tile.jpg`; wavs → cloud → faster-whisper medium `language=hi` (scratch `btx/tx.py`). PASS = identity + no cut + line verbatim + no stray speech in silent shots.
9. **Retakes**: viggle re-roll with fixed prompt (`docs/fix1.json`, ids `<id>b`) or protoface `python3 tools/run_clips2.py <ep> docs/shots.json <ids>` (cloud) → `renders/c2_<id>.mp4`.
10. **Assemble** (PC, launch via Start-Process): `docs/asm_ep04.py` pattern — OV map of overrides, normalize 1080×1920 25 fps crf17, concat, `loudnorm=I=-16:TP=-1.5:LRA=11`, srt, 720p preview. Deliver preview + `docs/qc-report.md` (lines verbatim count, fails + fixes, cost).

## B. Product ad / TVC / UGC (US, EN) — reference: projects/bench/docs/t01a, t02, t04
Product card (multi-view, text on card) + model chip + set card → 3–6 keyframes → viggle high (ar per item: 9:16 ad, 16:9 TVC) → whisper en → `python3 tools/bench_assemble.py <test> [9:16|16:9] [06=renders/c2_x.mp4]`. VO/lines native in the clip; never invent product text in video.

## C. Trailer / montage
Dialogue shots as in A. Montage beats: storyboard 3×4 board as @Image ref → protoface ref-to-video 15 s (≈54 cr) — the only place storyboard-to-video is allowed. Title/end cards with drawtext (Lato) in the device VM; BGM via `tools/gen.py music` (Suno) mixed at −18 dB under dialogue.

## D. Animation (stylized 3D)
Character sheet → Flow character → scene master (yes, for animation too) → keyframes → viggle high. Every clip: identical non-human voice-signature block; physics line for vehicle/character interaction ("passes beside, never over"); every named character visible in its keyframe.

## E. Dubbing
Regenerate the same shot with `dlg` in the target language (same refs, same prompt, language line swapped). Lips match; TTS overdub is not used.

## F. Whisper QC on cloud
```
cd <scratch>/btx && ffmpeg -i clip.mp4 -ac 1 -ar 16000 <id>_hi.wav && nohup python3 tx.py > out.txt &
```
(`tx.py`: faster-whisper medium int8; `_hi` → hi, `_es` → es, else en; prints `<id> | text`.)

## G. Transfers
PC → cloud: `device_stage_files`. Cloud → PC: `zip -0` (+ `split -b 19m`) → `device_commit_files` → `cat` + `unzip` + md5 check. Never commit raw mp4/jpg (bytes get altered).

## H. Version bump
Edit `knowledge/CHANGELOG.md` (new block on top) → `tools/capabilities.json` `_version`/`_rule`/`_drama_rule` → `CLAUDE.md` cost-law line → `.claude/agents/qc.md` gates → `.claude/skills/drama-series/SKILL.md` runtime line → `README.md` → project status doc. Cloud and PC both.

## I. Crun Seedance 2.0 FAST — the video lane (v7.4)
Host refs on litterbox (see above). `python3 projects/bench-intimate/docs/crunfast.py submit <id> <prompt.txt> <url1,url2> 480p 16:9 15` → `… poll <id>` → `renders/crunfast_<id>.mp4`. Model `bytedance/seedance2-0-fast-r2v`, 132 cr = $0.64 / 15 s, ~5 min. Backup #2 = Atlas (`prov.py atlas …`, $0.41, ~170 s). Identity = photo/portrait + character sheet as 2 refs. **SUPERSEDED 23 Sep 2026.** This line was a v7.3-era caveat written before Crun was the only lane. v7.4 made Crun every shot, and santan is costume-critical drama, chained, in Hindi — all three of the things this said never to do. What actually holds: the full character sheet must be an r2v ref (§L) or clothing drifts 3/3; chain within a location and reset at every location/time cut; Hindi dialogue works but must be whisper-checked because the prompt is in English. 

## J. Mode C — multi-shot ref-to-video (drama DEFAULT for dialogue scenes; v7.4 on Crun, refs ≤9)
**When:** same room, ≤2 speaking characters, ≤3 dialogue beats per clip, ≤15 s. Establishers, action, prop/vehicle "arrival", 3+ cast → Mode B (keyframe). 5–9 refs needed → same prompt on `protoface_h3` (viggle caps at 4 refs — docs: "at most 4 reference images", 1 ref video, no ref audio).

**Ref slots (Crun cap 9 — viggle table below still applies when a 4-ref lane is used; on Crun add the character sheets too):**
| cast | slot 1 | slot 2 | slot 3 | slot 4 |
|---|---|---|---|---|
| 1 | look portrait | character sheet | set (scene master) | last frame of previous clip |
| 2 | look portrait A | look portrait B | set | last frame |
| 3 | look A | look B | look C | last frame (carries the set) |
| first clip of a scene | … | … | set | scene master / keyframe (optional) |
Last frame goes in a **reference** slot, never first_frame (that is Mode A → hard-cut risk). Prompt line: "@Image4 = last frame of the previous clip: continue from this moment, same positions, same light."

**Look portrait rule:** the character ref is ALWAYS in that scene's costume. Per character per scene: Atlas GPT Image 2 edit (refs = master portrait + wardrobe card → 3/4 full-body, neutral bg, 1024x1536, $0.005) → QC face vs master portrait + outfit vs wardrobe card → `refs/v/char_<name>_<scene>.jpg`. Costume change (torn jacket, blood, new outfit) = new look portrait, 1 Flow job. Keep the COSTUME LOCK text line as a second lock. Real-photo cast: first look portrait uses the photo as `reference_images`, then the chip.

**Chain rule:** last-frame chain ≤3 clips, then restart from the scene master (refs soften over long chains). Extract: `ffmpeg -sseof -0.1 -i prev.mp4 -frames:v 1 -q:v 2 renders/<id>_last.jpg`.

**Manifest:** `{id, mode "B", dur 15, refs [look A, look B, set, last], ar, lane "viggle1080", dlg "line1 / line2 / …"}`. Prompt = header (one 15 s clip, THREE internal shots, cuts only at 5/10 s) + CHARACTERS STRICT LOCK (@Image1/@Image2 with face + outfit words) + @Image3 scene + @Image4 continuity + VOICE SIGNATURE + SHOT 1 | 0–5 s / SHOT 2 | 5–10 s / SHOT 3 | 10–15 s (each: framing, action, verbatim line or "No dialogue; lips stay closed", sound) + AUDIO + TECHNICAL/negative. Template `projects/redline/docs/v_c3-1.txt` (first clip) and `v_c3-2.txt` (chained clip).

**QC:** tile shows exactly 2 cuts (5 s, 10 s); whisper lines verbatim, one utterance each; identity + outfit both clips; deliver as H.264 (`-c:v libx264 -pix_fmt yuv420p -movflags +faststart`).

**Proof:** REDLINE scene 3 (rooftop, 6 shots, 34 s): Mode C 2 clips $0.30, 0 keyframes, 12 min, 4/4 lines, identity + outfit held, continuity via last frame — vs Mode B 6 clips $0.34 + 6 keyframes + 1 retake, ~45 min.

## K. Intimate / romance content rules (v7.4, locked 15 Sep)
Allowed: kiss, embrace, jacket/strap slipping, hands on waist/back/neck, silhouettes, lamp cut. Never: nudity, exposed chest, sexual touching, or a REAL person's face in any undress/body beat (use back-of-head / silhouette / hands-only framing; real face only in face shots). Prompt every clip with "clothes stay on / same outfit" + negatives (removed top, tank top, bare chest, male face). Expect Seedance to strip the man's shirt in body beats anyway → frame those as silhouette or hands. Reference: projects/afterhours (brief.md, v_ah-01/02b prompts, qc-report.md).

## L. Character-sheet template (Atlas GPT Image 2) — the identity anchor (v7.6)
Build BOTH characters' sheets before a drama chain; they become the r2v identity refs.
- Template files: `projects/afterhours/docs/csheet_<name>.txt` — 3 equal vertical panels in ONE frame: LEFT full-body FRONT, no head/neck/hair (invisible-body, hollow neckline = pure wardrobe); CENTER full-body REAR, head attached; RIGHT tight chest-up identity close-up. 18% grey seamless, flat shadowless catalogue light, true skin tone, 50mm, "photographed not generated". Fill IDENTITY + WARDROBE paragraphs per character.
- Run: `python3 tools/run_atlas_img.py projects/<proj> docs/csheet.json` → `refs/cs_<name>.png` (t2i, ~$0.004 each). QC the invisible-body front panel and the close-up face.
- Install as the project sheets: back up old (`cp x.jpg x.pre_csheet.bak.jpg`), then save the sheet as `refs/<name>_fullsheet.jpg` + a 1600px `_s.jpg`; manifests already point to `_s.jpg`.
- Why: full 3-panel sheet as r2v ref holds costume 4/4 (kills the shirt→tank strip) and identity across the chain. Proven: AFTER HOURS v6 Ring, 4/4 PASS.

## M. Crun Media Enhancer — finishing/upscale lane for 480p softness (v7.6, candidate — bench before locking)
Seedance FAST is 480p → assembled finals are soft. Crun's Media Enhancer skill does 4K image super-res + video frame-rate interpolation. Plan: run it on the ASSEMBLED final (not per clip) as the last post step, instead of changing the video lane. Not locked — bench one v6 clip first (quality vs. cost/time), then decide. Our lanes stay: video = Crun Seedance FAST, images = Atlas GPT Image 2.

## N. Crun upload reliability (v7.6)
litterbox can upload OK but 502 on ByteDance's fetch. Fix: seed ALL refs (sheets + each last frame) to uguu.se directly and cache in `renders/crun_urls.json` (key `rel:mtime`). Before re-submitting a FAILED id, delete its entry from `renders/crun_state.json` — the runner skips resubmit while a `tid` is present and will just re-poll the old failed task.

## O. Crun runner hardening (v7.7, 23 Sep 2026)
- `return_last_frame: true` is now sent on EVERY submit (r2v/i2v/t2v). Crun returns the last frame as an extra
  image entry in `result.media_urls` (e.g. `..._1.png`) — the runner downloads it to `renders/cr_<id>_last.png`.
  No more ffmpeg frame extraction for chaining.
- `CRUN_HOST=uguu` switches ref seeding to uguu.se. **Use it by default for new projects.** litterbox uploads
  succeed but ByteDance then fails to fetch them (`code 422: Failed to download media from the provided URL`),
  and re-uploading to litterbox does not help — only switching host does.
- Tiny-file guard: a finished mp4 under 100 KB is treated as MISSING by both the runner and the driver. The
  CDN (`static.mediaoss.bar`) intermittently stalls a download at ~192 KB; `--http1.1` and `-C -` do not rescue
  it. Park the partial, keep going, re-pull later — the task's `.json` keeps the media URL. The clip's
  last-frame PNG usually downloads fine, so **the chain survives a failed video download**.
- Driver `tools/santan_run.py` runs scenes sequentially, injecting the previous clip's last frame as the final
  ref. Each Bash call fits ~4–5 clips inside the 600 s tool cap; the runner is resumable, so just re-invoke.

## P. Moderation (v7.7)
Seedance rejects on register, not subject. Two real failures seen: `code 451 input` on romance wording
("camisole", "near-kiss"), and `code 451 output` on an energetic dance shot. Fix both by describing the thing as
what it is, modest/high-neckline wardrobe wording, calmer motion verbs — not by removing the scene.

## Q. Image lanes — live status (23 Sep 2026)
- `higgsfield-unlimited`: refused with *"No image model is unlimited-active on this account"* — entitlement was
  NOT active. Always let the refusal tell you; it never bills.
- `topview-unlimited`: ACTIVE, Nano Banana Pro (`nano_banana2`), 2K, 9:16, 0 credits. 6 character sheets in ~70 s.
- `flow-unlimited`: NOT connected to Claude sessions. Chrome being open does not connect an MCP server.
- Character-sheet QC: check the passport panel for a **cropped/half face** (split line running through the face) —
  hit once on SUMAN. Fix by demanding *"entire face fully visible and centred inside the left panel, both cheeks
  and both ears in frame, not cropped, face not touching the panel edge."*

## §R — 369 Studio Render deploy wiring (verified 23 Sep 2026)

- Repo: **`369network/369studio`**, branch `main`. There is no `369b` repo — that name was wrong in earlier notes.
- Service: `369studio`, Render service ID `srv-dalu0idbedkc738abl3g`, Docker, Starter, Singapore, Blueprint-managed.
- Live URL is **https://three69studio.onrender.com** (NOT `369studio.onrender.com` — Render rejected the leading digit). `PUBLIC_URL` in `render.yaml` still says the wrong one; fix it on the next code change.
- **Auto-Deploy gotcha:** Render's UI can show Auto-Deploy = "On Commit" while nothing ever deploys. The real switch is the **Render GitHub App installation**. Symptom: Account Settings → Account Security → Git Deployment Credentials → the GitHub entry expands to *"No repositories found"*, and the repo has no webhook under GitHub → Settings → Webhooks. Fix: install the Render GitHub App (`https://github.com/apps/render/installations/new`) scoped to the repo. Verified working 23 Sep 2026 — the credential now lists `369network/369studio`.
- Webhook only fires on **new** pushes; commits made while the app was missing never deploy on their own. Trigger a Manual Deploy once to resync.
- Env vars present: `ATLAS_KEY`, `CRUN_KEY`, `GLM_API_KEY`, `PUBLIC_URL`, `SUNOAPI_KEY`, `SUPABASE_ANON`, `SUPABASE_URL`.
  Still missing (declared `sync: false` in `render.yaml`, must be set by hand in the dashboard): **`VOICE_API_KEY`**, `SUPABASE_SERVICE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Nipam adds these himself — never paste a key into a web field.
- **Open risk:** Events log shows `Instance failed — ran out of memory (used over 512MB)` on 18 Sep. Starter plan is 512 MB; renders will trip it again. Either bump the compute plan or keep heavy work off the web dyno.

## §S — The clip ledger (`tools/ledger.py`, built 23 Sep 2026)

One SQLite index at `renders.db` (gitignored; rebuildable). Renders on disk stay the source of
truth — this joins them to task ids, credits, chain state and errors, which nothing did before.

```
python3 tools/ledger.py backfill --all      rebuild every project from state + sidecars
python3 tools/ledger.py cost [proj]         spend per project + metering coverage
python3 tools/ledger.py show <proj>         per-clip: status, seconds, MB, credits, chain, last-frame
python3 tools/ledger.py chain <proj>        which clips are BLOCKED because their chain ref is missing
python3 tools/ledger.py failed <proj>       ids needing a retake, and the exact retry command
```

Verified on backfill: total **5,061.0 credits ≈ $24.66**, matching an independent sum of every
`*.mp4.json` exactly. Two things the ledger found that nothing else could:
- **Double counting.** Manifest ids use hyphens (`ah-01`), `run_crun.py` writes underscores
  (`cr_ah_01.mp4`). Keyed naively that is two rows per clip and twice the cost. The ledger
  canonicalises on the underscored form.
- **Orphan sidecars** — a `.mp4.json` with no `.mp4` means we paid and got nothing.
  `afterhours/sd_04` is one (132.17 cr ≈ $0.64). These now show as `missing`, not silence.

### `run_crun.py` changes that go with it
- **`--retry` / `--force <ids>`** — clears those ids from `crun_state.json` first. Before this a
  FAILED clip could never be resubmitted: the failure handler left `tid` in place and the submit
  loop skips any id that has one. Hand-editing the state file was the only recovery.
- **`--dry-run`** — resolves every prompt file and ref and prints what is missing, **before** any
  spend. On santan it correctly shows s6 ready and s7 blocked (its chain ref does not exist yet).
- **Downloads are verified**: 3 attempts, return code and size both checked, `< CRUN_MIN_BYTES`
  (default **400 KB**, was 100 KB) is recorded as `truncated` rather than success. The old floor
  let `_old_v1/cr_s3.mp4` through at 196 KB with no moov atom.
- The sidecar is written **before** the download, so the media URL survives a failed transfer.
- A `success` status with empty `media_urls` is now a recorded failure, not a `KeyError` that
  killed the poll loop and abandoned every other in-flight clip.
- The `[ids…]` filter now applies to the poll phase too — a single-scene call no longer drags in
  every other unfinished scene in the project.

### Retired
`tools/_disabled/` now holds `santan_build.py` (v1 — wrote to the same paths as v2 and would have
silently regressed all 25 shared prompt docs to the old face-in-prompt template), `run_clips.py`,
`run_v4_clips.py`, `run_flow_kf2.py`. Per the deprecation rule: a disabled lane's runner moves out
of `tools/`, it does not sit there looking runnable.

## §T — Jev lane (typed text decisions), wired 23 Sep 2026

`tools/jev.py` + `.claude/skills/jev`. `POST https://api.typesafe.ai/v1/systemone`,
`Authorization: Bearer <JEV_API_KEY>`, model `jev-latest`.

**Request shape** (confirmed against docs.typesafe.ai, not guessed — the four 400s we ate in the
first evaluation came from guessing): `{state, model, questions}` where `questions` is an
**object keyed by your ids**. `choice` → `criteria` is a map option→description, max 255.
`score` → `criteria` is a list of 2–10 ordered levels. `noul` → no criteria, returns 0–1.
Responses carry `probabilities` and `confidence` for choice/score, plus `usage.input_tokens`.

**Verified behaviour:** the runner's local validation rejects a list-shaped `questions`, a
list-shaped choice `criteria` and a 1-level score before spending a call; a live `ping` reaches
the official API and returns a correctly diagnosed `401` with the stored jevai.org key — endpoint,
auth header and transport are right, only the key is wrong.

**Batch.** One call per *state*, not per question. TypeSafe's cookbook: 13 batched questions are
12.2× cheaper and 10× faster than 13 calls, same answers. The limit is 1,200 requests per
**minute**, so looping does not hit a ceiling — it just costs 12× more for nothing.

**Never visual.** Images/audio/video are unsupported. Frame QC stays in `.claude/agents/qc.md`.

**Key:** official only, from console.typesafe.ai, into `~/.config/keys_jev.env` (chmod 600).
Passed through a 0600 `curl -K` config, never argv. A jevai.org key does not work and must not be
used. Cost logged to `renders/jev_log.jsonl`; `python3 tools/jev.py cost` totals it.
