# 369 Studio — Creator backend (v1)

Real render service for the Creator app. Wraps the studio369 runners behind an HTTP API with a
credit wallet + ledger, and serves a live Creator page that produces **actual files**.

## What works now (tested 17 Sep 2026)
- **Image** → Atlas GPT Image 2 (`tools/run_atlas_img.py`). 5 cr. ✅ verified (1536×1024 PNG).
- **Video (text→video)** → Crun Seedance 2.0 FAST `bytedance/seedance2-0-fast-t2v` (added to `tools/run_crun.py`, mode `T`). 4s/480p = 128 cr. ✅ verified (mp4 out).
- Credits **held at submit, charged on success, refunded on failure** (failed job = 0 cr).
- Wallet + ledger in SQLite (`server/studio.db`). Single demo user.

## Run
```
cd studio369
pip install --break-system-packages fastapi 'uvicorn[standard]'
uvicorn server.app:app --host 0.0.0.0 --port 8080
# open http://localhost:8080
```
Keys reused from `~/.config/keys_crun.env` and `keys_atlas.env` (the runners load them).

## API
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/me` | — | `{wallet, ledger[]}` |
| POST | `/api/cost` | `{mode,model,res,dur}` | `{credits}` |
| POST | `/api/generate` | `{prompt,mode,model,res,dur,ar,audio}` | `{job_id,credits}` |
| GET | `/api/job/{id}` | — | `{status,credits,file?,err?}` |
| GET | `/api/file/{id}` | — | the mp4/png |
| GET | `/` | — | Creator UI |

## Credit model (`credits_for`)
- Image = 5 · Music = 60
- Video base: 4s=128, 8s=256, 15s=480 × res(480p 1.0 / 720p 1.6 / 1080p 2.4) × model mult
- Model mult: crun_fast 1.0 · frontier 1.4 · seedance25 1.8 · veo31_fast 1.6 · veo31 3.2 · kling_o3_pro 2.4 · pixverse 0.5
- Anchor: ~750 cr = $1 retail; crun_fast 15s ≈ our $0.64 real cost.

## Architecture
```
browser (creator.html)  ──fetch──▶  FastAPI (server/app.py)
                                       │  credits_for() → hold
                                       │  thread: subprocess run_crun.py / run_atlas_img.py
                                       │      (job dir server/jobs/<id>/{docs,gen.json,renders})
                                       │  on success → deduct + ledger, serve file
                                       ▼
                                   SQLite (wallet, ledger, jobs)
```

## Next (Phase 2+)
1. **Auth + multi-user wallet** → swap the SQLite `get_wallet/add_credits` for Supabase (users, wallets, ledger). Supabase already connected.
2. **Stripe** top-up/subscription → credits on payment webhook.
3. **QC gate** → after render, run tile+whisper (video) / sheet-check (image); expose `qc` in job status.
4. **r2v / i2v modes** → accept reference images (character sheets) for identity-locked shots; wire the other 13 apps to the same `/api/generate` with a `template`/`app` field.
5. **Deploy** → containerize; run on a box with the keys (not the artifact — artifacts can't fetch). Point a domain at it.
6. **Storage** → push outputs to R2/S3 instead of local `server/jobs`, return CDN URLs.

## Files
- `server/app.py` — the service
- `server/static/creator.html` — real Creator UI (fetches the API)
- `server/jobs/<id>/` — per-render working dir (gitignore)
- `server/studio.db` — wallet/ledger (gitignore)
- `tools/run_crun.py` — added mode `T` (text→video)

## Deploy (added)
Two paths:
1. **VPS + Docker** (simplest): `bash server/deploy.sh` → runs on :8080; put Caddy/nginx in front for TLS + domain. Mounts `~/.config` for render keys.
2. **Fly.io**: `server/fly.toml` included. `fly launch --no-deploy` once, then set secrets (CRUN_KEY, ATLAS_KEY, SUNOAPI_KEY, SUPABASE_ANON, SUPABASE_SERVICE_KEY, Stripe/R2…) and `fly deploy`. On Fly there is no `~/.config`, so the runners must read keys from env — set `CRUN_KEY`/`ATLAS_KEY`/`SUNOAPI_KEY` as secrets (run_crun/run_atlas already check env first; gen.py reads env).

## Apps on one API (added)
`server/templates.py` — 9 templates live: creator, marketing, shorts, vtemplate, sheets, influencer, music (Suno), author (needs TEXT_API_KEY), notes (needs TEXT_API_KEY). UI at `/app?app=<id>`. Character sheets/influencer auto-save a reusable character (r2v identity); Creator has an Identity picker that passes it as a ref.
