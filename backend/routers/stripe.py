"""Stripe payment router for UmaBuild.

Provides Checkout Session creation and Webhook handling for
subscription lifecycle management.
"""

import logging
import os
from typing import Any, Dict

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from middleware.auth import AuthUser, get_required_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe"])

# Stripe config
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")

# Supabase config for subscription management
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Frontend URLs
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


async def _upsert_subscription(data: Dict[str, Any]) -> None:
    """Upsert subscription record in Supabase via REST API."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase not configured, skipping subscription upsert")
        return

    url = f"{SUPABASE_URL}/rest/v1/subscriptions"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=headers, timeout=10.0)
            if resp.status_code not in (200, 201):
                logger.error("Subscription upsert failed: %s %s", resp.status_code, resp.text)
            else:
                logger.info("Subscription upserted for user %s", data.get("user_id"))
    except Exception as e:
        logger.error("Subscription upsert error: %s", e)


async def _update_subscription_by_stripe_id(
    stripe_subscription_id: str, updates: Dict[str, Any]
) -> None:
    """Update a subscription record by stripe_subscription_id."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return

    url = (
        f"{SUPABASE_URL}/rest/v1/subscriptions"
        f"?stripe_subscription_id=eq.{stripe_subscription_id}"
    )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(url, json=updates, headers=headers, timeout=10.0)
            if resp.status_code not in (200, 204):
                logger.error("Subscription update failed: %s %s", resp.status_code, resp.text)
            else:
                logger.info("Subscription updated: %s", stripe_subscription_id)
    except Exception as e:
        logger.error("Subscription update error: %s", e)


@router.post("/stripe/checkout")
async def create_checkout_session(
    request: Request,
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, str]:
    """Create a Stripe Checkout Session for subscription purchase.

    Requires authentication. Returns checkout URL for redirect.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="決済サービスが設定されていません")

    body = await request.json()
    plan = body.get("plan", "monthly")

    price_id = STRIPE_PRICE_YEARLY if plan == "yearly" else STRIPE_PRICE_MONTHLY
    if not price_id:
        raise HTTPException(status_code=400, detail="価格が設定されていません")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={
                "trial_period_days": 7,
                "metadata": {"user_id": user.user_id},
            },
            customer_email=user.email,
            metadata={"user_id": user.user_id},
            success_url=f"{FRONTEND_URL}/lab?upgraded=true",
            cancel_url=f"{FRONTEND_URL}/pricing",
        )
        return {"checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error("Stripe checkout error: %s", e)
        raise HTTPException(status_code=400, detail="チェックアウトセッションの作成に失敗しました")


@router.post("/stripe/portal")
async def create_portal_session(
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, str]:
    """Create a Stripe Customer Portal session for subscription management."""
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="決済サービスが設定されていません")

    # Look up Stripe customer ID from subscription
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="データベースが設定されていません")

    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/subscriptions"
            f"?user_id=eq.{user.user_id}"
            f"&select=stripe_customer_id"
            f"&limit=1"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                },
                timeout=5.0,
            )
            data = resp.json()

        if not data or not data[0].get("stripe_customer_id"):
            raise HTTPException(status_code=404, detail="サブスクリプションが見つかりません")

        session = stripe.billing_portal.Session.create(
            customer=data[0]["stripe_customer_id"],
            return_url=f"{FRONTEND_URL}/lab",
        )
        return {"portal_url": session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Portal session error: %s", e)
        raise HTTPException(status_code=400, detail="ポータルセッションの作成に失敗しました")


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Handle Stripe webhook events for subscription lifecycle.

    Events handled:
    - checkout.session.completed: Create subscription record
    - customer.subscription.updated: Update subscription status
    - customer.subscription.deleted: Downgrade to free
    - invoice.payment_failed: Mark as past_due
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set, accepting webhook without verification")
        event = stripe.Event.construct_from(
            stripe.util.convert_to_stripe_object(
                __import__("json").loads(payload),
                stripe.api_key,
            ),
            stripe.api_key,
        )
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except stripe.SignatureVerificationError:
            logger.error("Webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(event["data"]["object"])
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(event["data"]["object"])
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(event["data"]["object"])
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(event["data"]["object"])
    else:
        logger.debug("Unhandled webhook event: %s", event_type)

    return JSONResponse(content={"received": True})


async def _handle_checkout_completed(session: dict) -> None:
    """Handle checkout.session.completed — create subscription record."""
    user_id = session.get("metadata", {}).get("user_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        logger.warning("checkout.session.completed missing user_id in metadata")
        return

    # Retrieve subscription details from Stripe
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        status = "trialing" if sub.get("status") == "trialing" else "active"
        period_end = sub.get("current_period_end")
    except Exception:
        status = "active"
        period_end = None

    await _upsert_subscription({
        "user_id": user_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "plan": "pro",
        "status": status,
        "current_period_end": (
            __import__("datetime").datetime.fromtimestamp(
                period_end, tz=__import__("datetime").timezone.utc
            ).isoformat()
            if period_end else None
        ),
    })


async def _handle_subscription_updated(subscription: dict) -> None:
    """Handle customer.subscription.updated — update status."""
    sub_id = subscription.get("id")
    status = subscription.get("status", "active")
    period_end = subscription.get("current_period_end")

    # Map Stripe status to our status
    status_map = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
    }
    mapped_status = status_map.get(status, status)

    updates: Dict[str, Any] = {"status": mapped_status}
    if period_end:
        updates["current_period_end"] = (
            __import__("datetime").datetime.fromtimestamp(
                period_end, tz=__import__("datetime").timezone.utc
            ).isoformat()
        )

    await _update_subscription_by_stripe_id(sub_id, updates)


async def _handle_subscription_deleted(subscription: dict) -> None:
    """Handle customer.subscription.deleted — downgrade to free."""
    sub_id = subscription.get("id")
    await _update_subscription_by_stripe_id(sub_id, {
        "plan": "free",
        "status": "canceled",
    })


async def _handle_payment_failed(invoice: dict) -> None:
    """Handle invoice.payment_failed — mark as past_due."""
    sub_id = invoice.get("subscription")
    if sub_id:
        await _update_subscription_by_stripe_id(sub_id, {
            "status": "past_due",
        })
