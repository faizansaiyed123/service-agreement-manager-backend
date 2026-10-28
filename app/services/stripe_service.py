"""Stripe payment integration — create payment intents and verify webhooks."""
import logging
from decimal import Decimal
from typing import Any

import stripe
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Invoice, Payment

logger = logging.getLogger(__name__)


def _settings() -> Any:
    return get_settings()


def stripe_enabled() -> bool:
    s = _settings()
    return bool(s.stripe_enabled and s.stripe_secret_key)


def _client() -> Any:
    s = _settings()
    if not s.stripe_secret_key:
        raise DomainError(503, "stripe_not_configured", "Stripe is not configured")
    stripe.api_key = s.stripe_secret_key
    return stripe


def _stripe_error_response(exc: stripe.error.StripeError) -> dict[str, Any]:
    """Convert a Stripe SDK error into a structured error payload."""
    if isinstance(exc, stripe.error.CardError):
        return {
            "error": "card_declined",
            "code": exc.code or "card_error",
            "message": exc.user_message or str(exc),
            "decline_code": getattr(exc, "decline_code", None),
            "payment_intent": getattr(exc, "payment_intent", None),
        }
    if isinstance(exc, stripe.error.RateLimitError):
        return {"error": "rate_limited", "message": "Too many requests — please try again later"}
    if isinstance(exc, stripe.error.InvalidRequestError):
        return {"error": "invalid_request", "message": str(exc)}
    if isinstance(exc, stripe.error.AuthenticationError):
        return {"error": "stripe_auth_failed", "message": "Stripe API key is invalid or expired"}
    if isinstance(exc, stripe.error.APIConnectionError):
        return {"error": "stripe_network_error", "message": "Network error connecting to Stripe — please retry"}
    if isinstance(exc, stripe.error.APIError):
        return {"error": "stripe_api_error", "message": str(exc)}
    return {"error": "stripe_unknown", "message": str(exc)}


def create_payment_intent(invoice: Invoice, *, idempotency_key: str) -> dict[str, Any]:
    """Create a Stripe PaymentIntent for an invoice. Returns client_secret + payment_intent_id."""
    client = _client()
    amount_cents = int((invoice.total_amount * 100).quantize(Decimal("1")))
    if amount_cents <= 0:
        raise DomainError(400, "invalid_amount", "Invoice amount must be greater than zero")
    metadata = {
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "company_id": str(invoice.company_id),
    }
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=(invoice.currency or "usd").lower(),
            metadata=metadata,
            description=f"Invoice {invoice.invoice_number}",
            idempotency_key=idempotency_key,
            automatic_payment_methods={"enabled": True},
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe payment intent creation failed: %s", exc)
        raise DomainError(400, exc.code or "stripe_error", _stripe_error_response(exc)["message"]) from exc
    return {
        "payment_intent_id": intent.id,
        "client_secret": intent.client_secret,
        "amount": str(invoice.total_amount),
        "currency": invoice.currency or "usd",
    }


def record_stripe_payment(
    db: Session,
    invoice: Invoice,
    payment_intent_id: str,
    *,
    idempotency_key: str,
) -> Payment:
    """Record a Payment row after Stripe confirms the charge."""
    from app.api.billing import payment_fingerprint, replay_payment, event
    from app.schemas.billing import PaymentCreate

    payload = PaymentCreate(
        amount=invoice.total_amount,
        payment_method="card",
        reference=payment_intent_id,
        notes="Stripe online payment",
    )
    fingerprint = payment_fingerprint(invoice.id, payload)
    existing = replay_payment(db, invoice.company_id, invoice.id, idempotency_key, fingerprint)
    if existing is not None:
        return existing

    payment = Payment(
        company_id=invoice.company_id,
        invoice_id=invoice.id,
        amount=invoice.total_amount,
        payment_method="card",
        reference=payment_intent_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        notes="Stripe online payment",
        stripe_payment_intent_id=payment_intent_id,
        stripe_status="succeeded",
    )
    db.add(payment)
    db.flush()
    previous = invoice.status
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.invoice_id == invoice.id)
    ) or Decimal("0.00")
    new_covered = paid + invoice.total_amount
    invoice.status = "paid" if new_covered >= invoice.total_amount else "partially_paid"
    event(db, invoice, None, "invoice.payment_recorded", previous, {
        "payment_id": str(payment.id),
        "amount": str(invoice.total_amount),
        "payment_method": "card",
        "stripe_payment_intent_id": payment_intent_id,
    })
    db.commit()
    db.refresh(payment)
    return payment


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Verify a Stripe webhook signature and return the event payload."""
    s = _settings()
    if not s.stripe_secret_key:
        raise DomainError(503, "stripe_not_configured", "Stripe is not configured")
    stripe.api_key = s.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, s.stripe_webhook_secret or ""
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise DomainError(400, "invalid_webhook_signature", f"Webhook signature verification failed: {exc}") from exc
    return event