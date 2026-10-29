"""Stripe payment integration with server-side amount and payment verification."""
import hashlib
import logging
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import stripe
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Invoice, InvoicePortalToken, Payment, PaymentRefund

logger = logging.getLogger(__name__)

_ZERO_DECIMAL_CURRENCIES = {
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf",
    "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
}


def _settings() -> Any:
    return get_settings()


def stripe_enabled() -> bool:
    settings = _settings()
    return bool(settings.stripe_enabled and settings.stripe_secret_key)


def _client() -> Any:
    settings = _settings()
    if not settings.stripe_secret_key:
        raise DomainError(503, "stripe_not_configured", "Stripe is not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _minor_unit_factor(currency: str) -> Decimal:
    return Decimal("1") if currency.lower() in _ZERO_DECIMAL_CURRENCIES else Decimal("100")


def _to_minor_units(amount: Decimal, currency: str) -> int:
    return int((amount * _minor_unit_factor(currency)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _from_minor_units(amount: int, currency: str) -> Decimal:
    scale = Decimal("1") if currency.lower() in _ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
    return (Decimal(amount) / _minor_unit_factor(currency)).quantize(scale, rounding=ROUND_HALF_UP)


def _stripe_field(intent: Any, field: str, default: Any = None) -> Any:
    if hasattr(intent, "get"):
        return intent.get(field, default)
    return getattr(intent, field, default)


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


def create_payment_intent(
    invoice: Invoice,
    *,
    amount_due: Decimal,
    idempotency_key: str,
    invoice_portal_token_id: str | None = None,
) -> dict[str, Any]:
    """Create a Stripe PaymentIntent for the server-calculated outstanding balance."""
    client = _client()
    currency = (invoice.currency or "usd").lower()
    amount_minor = _to_minor_units(amount_due, currency)
    if amount_minor <= 0:
        raise DomainError(400, "invalid_amount", "Invoice amount must be greater than zero")

    metadata = {
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "company_id": str(invoice.company_id),
        "expected_amount": str(amount_due),
    }
    if invoice_portal_token_id:
        metadata["invoice_portal_token_id"] = invoice_portal_token_id

    try:
        intent = client.PaymentIntent.create(
            amount=amount_minor,
            currency=currency,
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
        "amount": str(amount_due),
        "currency": currency,
        "test_mode": str(_settings().stripe_secret_key or "").startswith("sk_test_"),
    }


def record_stripe_payment(
    db: Session,
    invoice: Invoice,
    payment_intent_id: str,
    *,
    idempotency_key: str,
    intent_data: Any | None = None,
) -> Payment:
    """Verify a successful Stripe charge, record it idempotently, and refund stale overpayments."""
    from app.api.billing import event, invoice_response, payment_fingerprint, refresh_invoice_status, replay_payment
    from app.schemas.billing import PaymentCreate

    client = _client()
    if intent_data is None:
        try:
            intent_data = client.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as exc:
            logger.error("Stripe payment intent verification failed: %s", exc)
            raise DomainError(502, "stripe_verification_failed", "Unable to verify the payment with Stripe") from exc

    intent_id = _stripe_field(intent_data, "id", "")
    if intent_id != payment_intent_id:
        raise DomainError(409, "payment_intent_mismatch", "The Stripe payment intent does not match the requested payment")
    if _stripe_field(intent_data, "status") != "succeeded":
        raise DomainError(409, "payment_not_succeeded", "Stripe has not confirmed this payment")

    metadata = _stripe_field(intent_data, "metadata", {}) or {}
    if metadata.get("invoice_id") != str(invoice.id) or metadata.get("company_id") != str(invoice.company_id):
        raise DomainError(404, "payment_intent_not_found", "This payment does not belong to the invoice")

    currency = str(_stripe_field(intent_data, "currency", "")).lower()
    if currency != (invoice.currency or "usd").lower():
        raise DomainError(409, "payment_currency_mismatch", "The Stripe payment currency does not match the invoice")

    received_minor = _stripe_field(intent_data, "amount_received", 0) or _stripe_field(intent_data, "amount", 0)
    try:
        received_amount = _from_minor_units(int(received_minor), currency)
    except (TypeError, ValueError):
        raise DomainError(409, "payment_amount_invalid", "Stripe returned an invalid payment amount") from None
    if received_amount <= Decimal("0.00"):
        raise DomainError(409, "payment_amount_invalid", "Stripe returned an invalid payment amount")

    # A browser confirmation and a Stripe webhook can report the same charge.
    # Deduplicate on Stripe's immutable intent ID as well as the API idempotency key.
    existing_intent = db.scalar(
        select(Payment)
        .where(Payment.stripe_payment_intent_id == payment_intent_id)
        .with_for_update()
    )
    if existing_intent is not None:
        if (
            existing_intent.company_id != invoice.company_id
            or existing_intent.invoice_id != invoice.id
            or existing_intent.amount != received_amount
        ):
            raise DomainError(409, "payment_intent_already_recorded", "This Stripe payment is already recorded against a different invoice or amount")
        return existing_intent

    payload = PaymentCreate(
        amount=received_amount,
        payment_method="card",
        reference=payment_intent_id,
        notes="Stripe online payment",
    )
    fingerprint = payment_fingerprint(invoice.id, payload)
    existing = replay_payment(db, invoice.company_id, invoice.id, idempotency_key, fingerprint)
    if existing is not None:
        return existing

    summary = invoice_response(db, invoice)
    refund_amount = received_amount if invoice.status == "void" else max(
        received_amount - summary.balance_due,
        Decimal("0.00"),
    )
    stripe_refund = None
    if refund_amount > Decimal("0.00"):
        try:
            stripe_refund = client.Refund.create(
                payment_intent=payment_intent_id,
                amount=_to_minor_units(refund_amount, currency),
                idempotency_key=f"sam-auto-refund:{payment_intent_id}",
            )
        except stripe.error.StripeError as exc:
            logger.error("Automatic refund for a stale invoice payment failed: %s", exc)
            raise DomainError(
                502,
                "automatic_refund_failed",
                "The invoice changed while payment was completing. Stripe could not automatically refund the excess; contact support.",
            ) from exc

    payment = Payment(
        company_id=invoice.company_id,
        invoice_id=invoice.id,
        amount=received_amount,
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

    if stripe_refund is not None:
        refund_fingerprint = hashlib.sha256(
            f"{payment_intent_id}:{refund_amount}:{stripe_refund.id}".encode()
        ).hexdigest()
        db.add(
            PaymentRefund(
                company_id=invoice.company_id,
                payment_id=payment.id,
                amount=refund_amount,
                refund_method="card",
                reference=stripe_refund.id,
                reason="Automatic refund because the invoice was voided or the charge exceeded its remaining balance.",
                idempotency_key=f"stripe-auto-refund:{payment_intent_id}",
                request_fingerprint=refund_fingerprint,
                created_by_user_id=None,
            )
        )
        db.flush()

    previous = invoice.status
    refresh_invoice_status(db, invoice)
    event(
        db,
        invoice,
        None,
        "invoice.payment_recorded",
        previous,
        {
            "payment_id": str(payment.id),
            "amount": str(received_amount),
            "payment_method": "card",
            "stripe_payment_intent_id": payment_intent_id,
            "automatic_refund_amount": str(refund_amount),
        },
    )
    if stripe_refund is not None:
        event(
            db,
            invoice,
            None,
            "invoice.payment_refunded",
            invoice.status,
            {
                "payment_id": str(payment.id),
                "stripe_refund_id": str(stripe_refund.id),
                "amount": str(refund_amount),
                "reason": "automatic_stale_payment_refund",
            },
        )

    now = datetime.now(UTC)
    if invoice.status == "void":
        db.execute(
            update(InvoicePortalToken)
            .where(
                InvoicePortalToken.invoice_id == invoice.id,
                InvoicePortalToken.status == "pending",
            )
            .values(status="revoked", used_at=now)
        )
    elif invoice_response(db, invoice).balance_due <= Decimal("0.00"):
        db.execute(
            update(InvoicePortalToken)
            .where(
                InvoicePortalToken.invoice_id == invoice.id,
                InvoicePortalToken.status == "pending",
            )
            .values(status="paid", used_at=now)
        )

    db.commit()
    db.refresh(payment)
    return payment


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Verify a Stripe webhook signature and return the event payload."""
    settings = _settings()
    if not settings.stripe_secret_key:
        raise DomainError(503, "stripe_not_configured", "Stripe is not configured")
    stripe.api_key = settings.stripe_secret_key
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret or ""
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise DomainError(400, "invalid_webhook_signature", f"Webhook signature verification failed: {exc}") from exc
    return event
