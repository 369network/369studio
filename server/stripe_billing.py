#!/usr/bin/env python3
"""369 Studio — Stripe billing (ready to wire; needs your keys).

Adds credit top-ups + subscriptions. On successful payment, the Stripe webhook
credits the user's Supabase wallet via the service-role `add_credits` RPC.

Wire it in server/app.py:
    from server.stripe_billing import router as billing_router
    app.include_router(billing_router)

Env needed (set before running):
    STRIPE_SECRET_KEY        sk_live_... / sk_test_...
    STRIPE_WEBHOOK_SECRET    whsec_...
    SUPABASE_URL             (already set)
    SUPABASE_SERVICE_KEY     service_role key (Supabase → Project settings → API)  ← KEEP SECRET, server-only
    PUBLIC_URL               e.g. https://369studio.app  (for success/cancel redirects)

Create Products/Prices in Stripe, then map price_id -> credits + plan in PLANS below.

Test:  pip install stripe ; stripe listen --forward-to localhost:8080/api/stripe/webhook
"""
import os, json, time, urllib.request
from fastapi import APIRouter, Request, HTTPException, Header

try:
    import stripe
except Exception:
    stripe = None

STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
SUPA_URL = os.environ.get("SUPABASE_URL", "https://jjyguuctlqgvlbzifpuv.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8080")
if stripe and STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

# price_id -> what the buyer gets. Fill with your real Stripe price IDs.
PLANS = {
    # one-time credit packs
    "price_topup_10k":  {"credits": 10000,  "plan": None},
    "price_topup_50k":  {"credits": 50000,  "plan": None},
    # monthly subscriptions (credits granted per successful invoice)
    "price_pro":    {"credits": 30000,  "plan": "pro"},
    "price_studio": {"credits": 75000,  "plan": "studio"},
    "price_agency": {"credits": 200000, "plan": "agency"},
}

router = APIRouter()

# Processed-webhook store, on the same mounted disk as the jobs DB.
_EVENTS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs", "stripe_events.db")
def _seen(event_id):
    """True if this Stripe event was already honoured. Insert wins the race; a duplicate raises."""
    import sqlite3
    try:
        c = sqlite3.connect(_EVENTS_DB, timeout=30)
        c.execute("CREATE TABLE IF NOT EXISTS ev(id TEXT PRIMARY KEY, ts INT)")
        try:
            c.execute("INSERT INTO ev(id,ts) VALUES(?,?)", (event_id, int(time.time()))); c.commit()
            return False
        except sqlite3.IntegrityError:
            return True
        finally:
            c.close()
    except Exception:
        return False        # never drop a real payment because bookkeeping failed

if STRIPE_SECRET and any(p.startswith("price_topup_") or p in ("price_pro","price_studio","price_agency") for p in PLANS):
    print("[stripe] WARNING: PLANS still holds PLACEHOLDER price ids — every checkout will 400 "
          "until they are replaced with real Stripe price ids, and they must match pricing.html.", flush=True)

def _add_credits(user_id, amount, item, plan=None):
    body = {"p_user": user_id, "p_amount": amount, "p_item": item, "p_plan": plan}
    req = urllib.request.Request(f"{SUPA_URL}/rest/v1/rpc/add_credits", data=json.dumps(body).encode(), method="POST")
    req.add_header("apikey", SERVICE_KEY); req.add_header("Authorization", f"Bearer {SERVICE_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

@router.post("/api/stripe/checkout")
async def checkout(request: Request, authorization: str = Header(None)):
    """Body: {price_id, mode:'payment'|'subscription'}. Returns {url} to redirect the buyer.

    SECURITY: this used to be unauthenticated and took `user_id` straight from the request body,
    so anyone could aim a credit grant at any account. The buyer is now whoever is signed in."""
    if not (stripe and STRIPE_SECRET):
        raise HTTPException(501, "Stripe not configured (set STRIPE_SECRET_KEY)")
    from server.app import auth_user, bearer
    user_id = auth_user(bearer(authorization))["id"]
    b = await request.json()
    price_id = b.get("price_id")
    if price_id not in PLANS: raise HTTPException(400, "unknown price")
    mode = b.get("mode", "payment")
    sess = stripe.checkout.Session.create(
        mode=mode, line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{PUBLIC_URL}/?paid=1", cancel_url=f"{PUBLIC_URL}/?canceled=1",
        client_reference_id=user_id, metadata={"user_id": user_id, "price_id": price_id},
    )
    return {"url": sess.url}

@router.post("/api/stripe/webhook")
async def webhook(request: Request, stripe_signature: str = Header(None)):
    if not (stripe and STRIPE_SECRET): raise HTTPException(501, "Stripe not configured")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, f"bad signature: {e}")
    # IDEMPOTENCY: Stripe retries a webhook on any non-2xx, including our own 500s, and each retry
    # used to grant credits again. Record every event id we have honoured and ignore repeats.
    if _seen(event["id"]):
        return {"ok": True, "duplicate": True}

    t = event["type"]
    if t == "checkout.session.completed":
        s = event["data"]["object"]; uid = s.get("client_reference_id") or (s.get("metadata") or {}).get("user_id")
        price = (s.get("metadata") or {}).get("price_id"); plan = PLANS.get(price, {})
        # A NEW subscription fires BOTH checkout.session.completed and invoice.paid for its first
        # period, which double-credited month one. Subscriptions are granted by invoice.paid only.
        if s.get("mode") == "subscription":
            return {"ok": True, "skipped": "subscription credited on invoice.paid"}
        if uid and plan: _add_credits(uid, plan["credits"], f"Stripe {price}", plan.get("plan"))
    elif t == "invoice.paid":  # subscription: first period and every renewal
        inv = event["data"]["object"]
        price = (((inv.get("lines") or {}).get("data") or [{}])[0].get("price") or {}).get("id")
        uid = inv.get("subscription_details", {}).get("metadata", {}).get("user_id") or inv.get("metadata", {}).get("user_id")
        plan = PLANS.get(price, {})
        if uid and plan: _add_credits(uid, plan["credits"], f"Stripe {price}", plan.get("plan"))
    return {"ok": True}
