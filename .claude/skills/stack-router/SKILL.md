---
name: stack-router
description: Runtime layer for the 115 ported MiniMax Design skills on Nipam's stack. Read FIRST whenever any minimax-skills:* skill, or any prompt, mentions a hub_* tool, MiniMax-H3, canvas, confirmation card, Seedance/Kling/Hailuo/Midjourney, or "check capabilities" — it maps every MiniMax-native tool, model, gate and canvas step to Higgsfield MCP / RunPod H3 / Pollo / ComfyUI / Artlist / ffmpeg / AskUserQuestion / project folders. Also the single source of truth for model routing, cost lanes and generation QC on this stack.
---

# Stack Router — MiniMax Design → Nipam's stack

The 115 MiniMax skills describe *what* to make. This file decides *how* on this stack. When a skill and this file disagree on a tool, model, canvas or gate, this file wins; the skill's creative methodology (phases, prompt contracts, QC lists) stays untouched.

## 0. Three laws (never break)

0. **Prompt reference:** `.claude/skills/nano-banana-prompt-finder` (40,986 image+video prompts, offline BM25 `find_prompt.py`) — search it before any card/poster/product/thumbnail image job with no supplied prompt and before montage/ad video prompts; `.claude/skills/seedance2-prompting` (6,278-prompt corpus + structure) compiles prompts for the Seedance backup lane and is the vocabulary bank for montage/ad/action/UGC prompts on every lane.
1. **Cost lanes (v7.8, 23 Sep 2026).** **Video: `seedance_fast_crun` only** (`tools/run_crun.py`, ~88 cr ≈ $0.43 / 10 s 480p). viggle / protoface / vgenv / fal / Flow video are DISABLED — their runners live in `tools/_disabled/`. **Images: prefer the ₹0 `topview-unlimited` MCP (Nano Banana Pro, `nano_banana2`); `atlas_gpt_image2` ($0.004 t2i / $0.005 edit-with-refs) is the paid fallback** when topview is unavailable or the job needs edit-with-refs. `flow-unlimited` is not MCP-connected; the `higgsfield-unlimited` entitlement was inactive on 22 Sep 2026. Never run bulk work on a per-call API. `tools/capabilities.json` is the normative source — a lane with `enabled: false` is refused by `gen.py`'s lane guard.
2. **Read live status, never assume:** before any Higgsfield job call `show_plans_and_credits` / `unlimited_status` and route only to models whose `unlimited_active` is true. Yesterday's activation does not count.
3. **No paid/GPU generation without a gate:** every "confirmation card" in a skill = one `AskUserQuestion` call (recommended option first, 3–5 options, one-line trade-off each, custom answer allowed). Batch parallel decisions into one call; ask dependent ones separately. Never ask "reply yes to confirm" in prose.

## 1. Tool-name map (MiniMax `hub_*` → here)

| MiniMax tool / phrase | Use on this stack |
|---|---|
| `hub_generate_image`, `midjourney_image_generation`, `image_generation` | Higgsfield `generate_image` (batch: `generate_image_batch` + `jobs_wait`) → Pollo `nano-banana-2` via `pollo_api.py` → local ComfyUI Z-Image Turbo (character ID packs) |
| `hub_generate_video`, `video_generation`, "MiniMax H3" | RunPod H3 via `h3-runpod-lane` + `h3-shot-prompting` → Higgsfield `generate_video` (unlimited-active only) → Pollo/poyo → fal (approval) |
| `hub_generate_audio_speech`, `audios_generation`, `speech-2.8-hd`, `seed-audio-1.0` | Higgsfield `generate_audio` (activate audio bundle: text2speech_v2 / inworld_tts / seed_audio) → ElevenLabs key → Artlist `generate_voiceover` |
| `hub_voice_prepare`, `get_voice_id` | Higgsfield `list_voices` / `create_voice` (consent statement mandatory for clones) |
| `hub_generate_audio_music`, `music_generation_*`, `music-3.0` | Artlist `generate_music` (unlimited) → Higgsfield `generate_audio` (mirelo) |
| `hub_analyse_media` | Images: `Read` the file. Video: ffmpeg keyframe tile (`fps=1,tile=4x4`) then `Read`. Metadata: `ffprobe`. |
| `hub_media_transcribe` | `faster-whisper` (small, int8) in the container → SRT |
| `hub_subtitle_format` + burn-in | ffmpeg ASS/SRT with `subtitles=<absolute path>`; safe area: top 1/8, bottom 1/4, sides 7%; 9:16 ≤7 EN words/line, 16:9 ≤14 |
| `hub_ffmpeg`, `merge_videos`, timeline tools, `clip-export` | ffmpeg in the container (concat, `loudnorm=I=-16:TP=-1.5:LRA=11`, mux). CapCut/JianYing draft: `clip-export` skill's pyJianYingDraft scripts on the Windows PC via Desktop Commander |
| `hub_image_search`, Pinterest research | `WebSearch` / Chrome; save picks into `/refs` |
| `hub_list_capabilities`, `pre_generation_window_check` | §3 table + live `show_plans_and_credits` |
| `hub_canvas_write_node`, `hub_canvas_group_recent_outputs`, "write to canvas" | Project folder (§4). Candidate picking = Artifact gallery or numbered image list |
| `hub_plan_write / patch_stage / get_stage_detail / replan` | `plan.json` in the project folder (§5) |
| `question`, "confirmation card", "card popup", "ToolConfirmCard" | `AskUserQuestion` |
| `hub_memory` | Claude memory — durable anchor ids only |
| `hub_select_image_recipe` | `references/poster.md` (clone its skeleton for other verticals) |
| `H3-Context-IR`, `hub` prompt expansion | Rewriter lane, cheapest first: (a) HF Space `hugging-apps/minimax-h3-prompt-rewriter` (free, text-only, manual); (b) `lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA` on Qwen3.6-27B, run on the RunPod box next to H3 (`infer.py --prompt … --duration N --resolution 16:9 --greedy` → integrated_multimodal_description / overall_soundscape / non_diegetic_music, i.e. the `h3-shot-prompting` contract); (c) official `POST https://api.minimax.io/v2/h3_context_ir` (Bearer key; content[] text + image/video/audio refs with roles first_frame/last_frame/reference_*; duration 4–15; ratio) → poll `/v2/video-generation-v2-query` → `content.prompt`. Token-billed, returns prompt only — the one paid_api call allowed without per-job approval because it costs cents and the render stays on RunPod. Always run the `h3-shot-prompting` pre-flight on the rewritten prompt. |
| `H3-Regenerate-2K`, IR2K ComfyUI workflows | Two lanes. Free: Higgsfield `upscale_video` on the 768P render. Official (paid_api, hero shots only, per-clip approval): `POST https://api.minimax.io/v2/video_regeneration` body `{model:"MiniMax-H3", resolution:"2K", content:[{type:text,text:<the FINAL prompt actually sent to H3>}, {type:video_url, video_url:{url:<768P mp4, data-URL or public>}, role:"base_video"}, …original refs with original roles]}` → poll `GET /v2/query/video_generation/<task_id>` → `task.content.url`. Source must be a genuine H3 768P output: 24 fps, dims ÷32, 768×768…768×1344, 107–362 frames, audio track present; billed on output seconds. LightX2V = faster H3 runtime on RunPod (offloading, quantized) |
| Panorama Viewer plugin | `360-panorama-viewer` pattern (happycapy): generate 2:1 equirectangular panoramas (Higgsfield GPT Image / Nano Banana, prompt: "360 degree equirectangular panorama, 2:1, seamless tiling for VR"), resize 1774×887, seam-fix by `np.roll` offset search, base64 into a single three.js HTML → publish as Artifact. SKU: 360 property/venue tours |
| Feishu/Lark intent gate, `lark-cli` | Not connected; ignore |

## 2. H3 prompt contract (self-hosted, from MiniMax's own vendor card)

Full card: `references/vendors/minimax.md` (Chinese, authoritative). Compile every H3 prompt as:

```
全局基准 (global base: subject, scene, style + 2–4 observable traits — inherited by all shots)
【镜头1】 shot size (大全景/全景/中景/中近景/近景/特写) → camera move (start/path/end) → subject action beat → important background motion → dialogue / SFX / explicit silence
【镜头2】 … 【镜头N】
```
- Refs by slot: `@图片1 @图片2 … @视频1 @音频1` in the exact order sent; state each slot's role. Never list filenames.
- Shot count by duration: 5 s = 2–3, 6–10 s = 3–5, 11–15 s = 5–7. POV / one-take / continuous-follow wording collapses to ONE shot. Calm/lyrical scenes: −1–2 shots, one slow move.
- Every shot names its sound (dialogue verbatim with speaker, or SFX/ambience, or explicit mute). Speaker tags `(S1)`, Character Voice Signature block per speaking role for dialogue-bearing clips.
- Budget 7000 chars/prompt; over → split into continuation items `sg_04a/sg_04b`, each ≤ `max_generated_clip_duration_s` (default 15).
- Self-hosted limits: 768P native (16:9 = 1344×768, 9:16 = 768×1344, 1:1 = 768×768), 24 fps, 5–15 s, 6 ratios. Concurrency = RunPod worker count (default 2), never assume MiniMax's 10.
- Other vendors' grammars when routed there: Seedance omits shot size/camera by default; Seedream one medium per sentence + `Image 1: face…` role syntax; Midjourney English only, `--ar --s --chaos --no`; in-image text ceilings banana CN≤8/EN≤5, seedream CN≤8/EN≤10, gpt-image unbounded. Cards: `references/vendors/`.

## 3. Capabilities table (refresh weekly; live status always wins)

| Task | Primary (unlimited) | Fallback | Notes |
|---|---|---|---|
| General image, cleanup, identity consistency | Higgsfield Nano Banana / Nano Banana Pro (2k cap) | Pollo nano-banana-2 (~$0.10 @2K) | `width`+`height` mandatory; refs via `media_import_url` → `{"type":"media_input","id"}` |
| Style-ref, text-in-image, layout, storyboard grids | Higgsfield GPT Image | Pollo gpt-image-2-0 | 3 same-model prompt-preserving retries, then ask |
| Anime / webtoon / sequential batches | Higgsfield Seedream 4.5 / 5.0 Lite | — | `sequential` mode for cross-image consistency |
| Photoreal character ID packs, turnarounds | local ComfyUI Z-Image Turbo | FLUX.2 Pro (Higgsfield) | multi-view sheet = one 16:9 image, 3×2 grid default |
| H3 prompt rewriting (Context-IR) | LoRA rewriter on RunPod / HF Space | official `/v2/h3_context_ir` (cents, prompt only) | needed for every H3 clip; never skip pre-flight |
| Video with native speech, identity-locked drama/ad shots | **viggle_h3 quality=high 1080p ($0.01/s, PC runner) → whisper QC → failed shots on protoface_h3 768p + refs** | vgenv_h3 (drafts only); fal h3-max-turbo (no refs); fal 2K (ask). TopView = images only | ONE shot per clip ≤6 s, camera locked, 'no transitions'; @Image1/@Image2/@Image3 roles in prompt; H3 grammar §2; QC per clip |
| Persistent character + keyframes (drama) | **flow-unlimited**: `create_character` from the master portrait, then `generate_image(reference_assets=[names], reference_images=[scene grid])` x2 (0 credits, ~90 s per shot, identity 16/16 on Hisaab v4) | Higgsfield NB Pro (slow, drifts) |
| Character bible (client-facing only) | Higgsfield NB Pro `nano-banana-2` with `knowledge/templates/character-bible-prompt.md` | FLUX.2 Pro | input = ONE large distinctive front portrait (real-photo texture). NB Pro drifts on AI-generic faces (Riya v1–v3, 14 Sep) — for existing characters keep the proven 3-view sheet + keyframe as video refs |
| Product-consistency multi-shot, no H3 | Higgsfield Kling 3.0 | Pollo Kling / Seedance 2 | seedance_2_0 / wan2_7 / gemini_omni are activatable (720p when unlimited) |
| Premium 8 s cinematic (Veo) | Google Flow via `flow-mcp` (subscription) | kie.ai flat-per-clip | Veo is never unlimited on Higgsfield |
| Motion-control / dance from driving video | Higgsfield `motion_control` | Pollo jimeng | — |
| TTS narration / dialogue | Higgsfield text2speech_v2 / inworld_tts | ElevenLabs API | trim voice refs feeding video to ≤3 s |
| Cinematic dub, clone, soundscape+dialogue | Higgsfield seed_audio | — | consent statement before any clone |
| BGM / score / song | Artlist `generate_music` | Higgsfield mirelo | one BGM bed per project, trimmed in post; songs need confirmed lyrics |
| Upscale / reframe / bg removal | Higgsfield `upscale_video` / `upscale_image` / `reframe` / `remove_background` | — | upscale stage mandatory after H3 |
| 3D scene / previz | Higgsfield `scene_builder_3d_*` / Blender via `blender-workflow` | — | replaces Director Stage |

Higgsfield operating limits: ≤6 concurrent submissions (workspace limit 8, shared); Turnstile 403 after ~45–55 jobs — stop, solve in browser, restart local MCP; always `wait:false` + poll (`jobs_wait` / `check_job`); session expires ~daily.

## 4. Folder-as-canvas convention

```
/projects/<slug>/
  brief.md            intake + locks (ratio, resolution, audio approach, language)
  plan.json           Stage Execution Plan (§5)
  refs/               user + researched references (numbered: 01-product.jpg …)
  assets/characters|scenes|props|voices/   reusable anchors, one file per anchor id
  docs/               storyboard.md, shot-list.md, scripts, generation-strategy.md
  renders/<stage>/    generated media, filename = work item `name`
  final/              <slug>_final.mp4 + subtitle files if requested
  asset-manifest.json {anchor_id → path, role, contributes}
```
- A generation is "done" only when the file is in `renders/` and its path is written to `plan.json` runtime refs (canvas node id ≡ path).
- Never rename generated files; friendly names go in chat. Partial doc edits = anchored `Edit`, never full rewrite.
- Candidate picking (visual research, 3 creative routes): show numbered images (Artifact gallery for >4), user answers by number in chat — no `AskUserQuestion` for that.
- Auto-group: after a turn that produced ≥2 assets, list them under one label in the reply.

## 5. `plan.json` — Stage Execution Plan (compact schema)

```json
{"plan_id":"", "workflow":{"path":"","variant":null}, "sources":[{"id":"","kind":"uploaded_script|canvas_brief|user_ref|external_file","path":"","execution_excerpt":""}],
 "stage_outline":[{"id":"","order":1,"name":""}],
 "stages":[{"stage_id":"","order":1,"goal":"","depends_on":[],
   "review":{"before_execution":[],"after_execution":[]},
   "stage_fields":{"max_generated_clip_duration_s":15,"execution_policy":"parallel_independent_work_items"},
   "execution_locks":[{"aspect_ratio":"9:16"},{"resolution":"768P+upscale"},{"vendor_model_policy":"h3_runpod"}],
   "ref_capsules":[{"id":"","name":"","role":"character|product|scene|style|layout","contributes":"","take":"preserve|adapt","path":""}],
   "work_items":[{"id":"","name":"","modality":"image|video|audio.tts|audio.music|postprocess|document","refs":[],"source":{},"render":{"duration_target_s":0,"audio_approach":"native dialogue + SFX/ambience"},"prompt":""}],
   "constraints":[{"rule":""}],
   "runtime":{"status":"waiting_user|doing|done|blocked","waiting_reason":"plan_review|result_review","runtime_refs":{},"failed_item_ids":[],"retry_count":0}}]}
```
Rules: author one stage at a time; one work item per continuity clip group; `audio_approach` stated positively (`silent` only with explicit evidence); prompts dispatched byte-for-byte; retries only for failed ids; never reuse a stage confirmation; prefix stages before the current one are frozen. Full contract: `references/workflows/stage-execution-plan.md`; agent roles: `references/workflows/{router,planner,executor}.md` (rename hub_* per §1 when using them as subagent prompts).

## 6. Always-on contracts (apply in every generation turn)

- **Semantic judgment** (`references/contracts/semantic-judgment.md`): before any ref-bearing generation assign each ref a role (source/edit, layout, style/design, character/scene, mood) and a decision (take / adapt / ignore / block / ask); prompt = user request → ref roles → required carry-over traits. Ignore decisions stay silent. Colors only from user text or approved palette.
- **Anti-loop** (`references/contracts/anti-loop.md`): same tool + same substantive args 3× in 5 calls → stop, change approach or ask. Max 3 distinct retries per operation.
- **Baseline**: never rename/move outputs; working language = user's chat language (Hinglish for Nipam), deliverable language = what the skill/brief locks (default US English for audience-facing).
- **Failure cards** (`references/failures/`): read only when the risk is present — ref binding → `character-refs`; short edit → `intent-overreach`; dialogue video → `spoken-video`; faces/hands → `anatomy-traps`; text in image → `on-image-text`; real logos → `brand-injection` (never redraw a real logo; client supplies files).

## 7. Policy flags (say it, then do it)

- AI-generated UGC/testimonial/KOC videos: label as AI on Meta/TikTok; never present as real customers.
- Voice clones: written consent on file before `create_voice`.
- Real brand logos/product photos: use client-supplied verified files only.

## 8. Reference index

- `references/vendors/*.md` — 14 MiniMax vendor cards (minimax = H3 grammar; seedance, seedream, banana, gpt-image, midjourney, kling-omni, veo, wan, jimeng, moss, seed-audio, seedaudio, official-music)
- `references/failures/*.md` — 13 decision-test cards
- `references/contracts/` — semantic-judgment, anti-loop, baseline
- `references/workflows/` — stage-execution-plan, asset-pipeline, audio-pipeline, subtitle-pipeline, video-merge, router/planner/executor role prompts
- `references/poster.md` — image recipe skeleton
