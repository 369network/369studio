#!/usr/bin/env python3
"""369 Studio — output storage adapter (R2 / S3). Ready to wire; needs creds.

By default renders are served from local disk (server/jobs/<id>/...). For production,
push each finished file to Cloudflare R2 (or any S3) and serve a public/CDN URL.

Env:
    R2_ENDPOINT      https://<accountid>.r2.cloudflarestorage.com
    R2_BUCKET        369studio-renders
    R2_ACCESS_KEY / R2_SECRET_KEY
    R2_PUBLIC_BASE   https://cdn.369studio.app   (bucket's public/custom domain)

Use in app.py run_job after QC:
    from server.storage import put_output
    url = put_output(out, f"{jid}{ext}")     # returns public URL or None
    if url: setj(jid, file=url)              # store URL instead of local path; /api/file can 302 to it
"""
import os
try:
    import boto3
except Exception:
    boto3 = None

R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")
R2_BUCKET   = os.environ.get("R2_BUCKET", "")
R2_KEY      = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET   = os.environ.get("R2_SECRET_KEY", "")
R2_PUBLIC   = os.environ.get("R2_PUBLIC_BASE", "")

def _client():
    if not (boto3 and R2_ENDPOINT and R2_KEY): return None
    return boto3.client("s3", endpoint_url=R2_ENDPOINT,
                        aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET, region_name="auto")

def put_output(local_path, key):
    """Upload local_path to the bucket under key; return public URL, or None if storage unconfigured."""
    c = _client()
    if not c: return None
    ctype = "video/mp4" if key.endswith(".mp4") else ("image/png" if key.endswith(".png") else "application/octet-stream")
    c.upload_file(local_path, R2_BUCKET, key, ExtraArgs={"ContentType": ctype})
    return f"{R2_PUBLIC.rstrip('/')}/{key}" if R2_PUBLIC else None
