"""Email draft generation service."""

import json
import logging

from sqlalchemy.orm import Session

from app.llm.client import get_llm_client
from app.logging_config import StepTimer, log_event
from app.models import ActionCard, EmailDraft

logger = logging.getLogger("app.draft_generator")


def _build_context(card: ActionCard) -> str:
    extraction = card.extraction
    parts = []

    if extraction.amount:
        parts.append(f"Amount: ${extraction.amount:.2f}")
    if extraction.currency and extraction.currency != "USD":
        parts.append(f"Currency: {extraction.currency}")
    if extraction.renewal_date:
        parts.append(f"Renewal date: {extraction.renewal_date}")
    if extraction.return_deadline:
        parts.append(f"Return deadline: {extraction.return_deadline}")
    if extraction.warranty_end_date:
        parts.append(f"Warranty expires: {extraction.warranty_end_date}")
    if extraction.free_trial_end_date:
        parts.append(f"Trial ends: {extraction.free_trial_end_date}")
    if extraction.cancellation_deadline:
        parts.append(f"Cancellation deadline: {extraction.cancellation_deadline}")
    if extraction.cancellation_policy:
        parts.append(f"Cancellation policy: {extraction.cancellation_policy}")
    if extraction.old_price and extraction.new_price:
        parts.append(f"Price change: ${extraction.old_price:.2f} -> ${extraction.new_price:.2f}")
    if card.description:
        parts.append(f"Issue: {card.description}")

    return "\n".join(parts) if parts else "No additional context available."


def generate_draft(
    card: ActionCard, db: Session, tone: str = "professional", user_id: str = ""
) -> EmailDraft:
    if card.email_draft:
        log_event(logger, logging.INFO, "draft_cache_hit",
                  action_card_id=card.id, draft_id=card.email_draft.id)
        return card.email_draft

    merchant = card.extraction.merchant or "the service"
    context = _build_context(card)

    with StepTimer() as timer:
        client = get_llm_client()
        raw_result = client.draft_email(card.action_type, merchant, context, tone=tone)

    log_event(logger, logging.INFO, "draft_generated",
              user_id=user_id or card.user_id,
              action_card_id=card.id,
              action_type=card.action_type,
              merchant=merchant,
              tone=tone,
              subject=raw_result.get("subject", ""),
              body_chars=len(raw_result.get("body", "")),
              elapsed_ms=timer.elapsed_ms)

    draft = EmailDraft(
        user_id=user_id or card.user_id,
        action_card_id=card.id,
        subject=raw_result.get("subject", f"Regarding {merchant}"),
        body=raw_result.get("body", ""),
        raw_llm_response=json.dumps(raw_result),
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)

    return draft
