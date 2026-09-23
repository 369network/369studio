---
vendor: atlas-gpt-image2
modality: image
status: active
provider: Atlas Cloud (OpenAI GPT Image 2)
backend: atlas
lane: atlas_gpt_image2
runner: tools/run_atlas_img.py
---

# atlas-gpt-image2 — the paid image lane

The image lane that produces the character sheets, wardrobe cards, location cards, prop cards and look portraits
that the Crun video lane uses as references. **Lane order: the ₹0 `topview-unlimited` MCP (Nano Banana Pro, 2K)
first; Atlas is the paid fallback — and the one to use whenever a job needs edit-with-refs.**

## API

- Base: `https://api.atlascloud.ai/api/v1/model`
  - `POST {base}/generateImage` → `data.id` (a prediction id)
  - `GET  {base}/prediction/<id>` → `data.status` ∈ `completed | succeeded | failed | timeout | <pending>`, `data.outputs[0]` = the image URL
- Auth header: **`Authorization: Bearer <ATLAS_KEY>`**, plus `Content-Type: application/json`.
- Key resolution: `$ATLAS_KEY` → `~/.config/keys_atlas.env` → `<root>/.config/keys_atlas.env`. Never printed.
- Transport is `curl`; the runner polls every 10 s up to 1200 s.

## Models — t2i vs edit-with-refs

| Job shape | `model` | Extra body field | Cost |
|---|---|---|---|
| No `refs` in the job | `openai/gpt-image-2/text-to-image` | — | **$0.004** |
| `refs: [...]` present | `openai/gpt-image-2/edit` | `images: [url…]` | **$0.005** |

Refs are **local project-relative paths** in the job file; the runner uploads each one to litterbox (72 h,
4 attempts with backoff) and caches the URL in `renders/crun_urls.json` keyed `rel:mtime` — the **same cache the
Crun runner uses**, so a ref uploaded for one lane is reused by the other.

## Request body (exactly what `run_atlas_img.py` sends)

```json
{ "model": "openai/gpt-image-2/edit",
  "prompt": "<inline text, or the contents of the .txt named in the job>",
  "size": "1024x1536",
  "n": 1,
  "images": ["https://litterbox…/portrait.png"] }
```

## Jobs file and sizes

`jobs.json` is a list of `{"id", "prompt", "refs": [...], "size", "n"}`.
- `prompt` is either inline text or a path ending in `.txt`, resolved relative to the project (e.g. `docs/csheet_suman.txt`) and read as the full prompt.
- `size`: `1024x1024` · `1024x1536` (default, the portrait/sheet size) · `1536x1024` · `2048x2048`.
- `n` defaults to 1.

## Where output lands

- Image → **`projects/<proj>/refs/<id>.png`** — i.e. straight into the ref folder the video manifests point at.
- Receipt → `projects/<proj>/renders/img_<id>.json` (the full prediction record).
- Resume state → `projects/<proj>/renders/atlas_img_state.json` (keyed by job id, holds `pid`).
- **Resumable and idempotent:** a job whose `refs/<id>.png` already exists with non-zero size is skipped, and a
  job that already has a `pid` is not resubmitted — delete the png (and its state entry) to force a redo.
- Failures print `FAIL <id> <error>` and are recorded in the state file; they are not retried automatically.

```bash
python3 tools/run_atlas_img.py projects/<proj> docs/<proj>_jobs.json          # all jobs
python3 tools/run_atlas_img.py projects/<proj> docs/csheet.json cs_suman      # one id
```

## The character-sheet template (RUNBOOK §L) — the main reason this lane exists

`projects/<proj>/docs/csheet_<name>.txt`: 3 equal vertical panels in ONE frame — LEFT full-body FRONT with no
head/neck/hair (invisible-body, hollow neckline = pure wardrobe), CENTER full-body REAR with head attached,
RIGHT tight chest-up identity close-up. 18% grey seamless, flat shadowless catalogue light, true skin tone,
50 mm, "photographed not generated". Run as t2i (~$0.004), QC the invisible-body front panel and the close-up
face, then install as `refs/<name>_fullsheet.jpg` plus a 1600 px `_s.jpg` (back up the old one first).
**Why it matters:** the full sheet as a Crun r2v ref holds costume 4/4 and identity across the chain.

Look portraits are the edit path: refs = master portrait + wardrobe card → 3/4 full-body, neutral background,
`1024x1536`, $0.005 → `refs/v/char_<name>_<scene>.jpg`.

## QC before spending video money

- The passport / close-up panel must not have a **cropped or half face** (a split line through the face — hit
  once on SUMAN, RUNBOOK §Q). Fix by demanding *"entire face fully visible and centred inside the left panel,
  both cheeks and both ears in frame, not cropped, face not touching the panel edge."*
- A bad sheet poisons every clip that references it: $0.005 to redo here versus ~$0.43 per clip there.

## When NOT to use this

- **When the ₹0 `topview-unlimited` lane can do the job** (plain t2i sheets and cards, 2K, 9:16). Atlas is the
  paid fallback — use it for edit-with-refs and when topview is unavailable.
- **For video.** This lane is images only; every moving frame belongs to `crun-seedance`.
- **For the final deliverable's pixels.** These are production references, not shipped artwork.
- **When the ref file is not on disk yet** — refs must be local paths the runner can upload; there is no
  pass-a-URL path in the job format.
- **To patch one panel of a bad sheet.** Regenerate the whole sheet; it costs cents and a patched sheet drifts.

## Pointer
→ `knowledge/RUNBOOK.md` §L (sheet template) §Q (image lanes, cropped-face fix) → `knowledge/vendors/gpt-image.md`
(GPT Image prompt behaviour and known bugs) → `knowledge/vendors/crun-seedance.md` (what consumes these refs)
→ `.claude/agents/qc.md` (the gate)
