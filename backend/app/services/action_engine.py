"""Rule-based action card generator."""

import logging

from sqlalchemy.orm import Session

from app.logging_config import StepTimer, log_event
from app.models import ActionCard, Extraction
from app.utils.date_helpers import days_until, human_time_description, urgency_level

logger = logging.getLogger("app.action_engine")


def generate_action_cards(extraction: Extraction, db: Session, user_id: str) -> list[ActionCard]:
    """Evaluate extraction data against rules and create action cards."""
    cards: list[ActionCard] = []

    if extraction.subscription_status == "active" and extraction.renewal_date:
        days = days_until(extraction.renewal_date)
        if days is not None and 0 <= days <= 30:
            amount_str = f"${extraction.amount:.2f}/mo" if extraction.amount else ""
            cards.append(ActionCard(
                user_id=user_id,
                extraction_id=extraction.id,
                action_type="cancel_subscription",
                title="Cancel this subscription?",
                description=(
                    f"{extraction.merchant or 'This service'} renews "
                    f"{human_time_description(days)} for {amount_str}".strip()
                ),
                urgency=urgency_level(days),
                deadline=extraction.renewal_date,
            ))

    if extraction.return_deadline:
        days = days_until(extraction.return_deadline)
        if days is not None and 0 <= days <= 30:
            cards.append(ActionCard(
                user_id=user_id,
                extraction_id=extraction.id,
                action_type="return_item",
                title="Return window closes soon",
                description=(
                    f"You have {human_time_description(days)} to return your "
                    f"{extraction.merchant or ''} purchase"
                    + (f" (${extraction.amount:.2f})" if extraction.amount else "")
                ),
                urgency=urgency_level(days),
                deadline=extraction.return_deadline,
            ))

    if extraction.refund_opportunity:
        cards.append(ActionCard(
            user_id=user_id,
            extraction_id=extraction.id,
            action_type="request_refund",
            title="Possible refund opportunity",
            description=extraction.refund_opportunity,
            urgency="medium",
        ))

    if extraction.price_increased and extraction.old_price and extraction.new_price:
        pct = round(((extraction.new_price - extraction.old_price) / extraction.old_price) * 100)
        cards.append(ActionCard(
            user_id=user_id,
            extraction_id=extraction.id,
            action_type="bill_increase_alert",
            title=f"Price increased {pct}%",
            description=(
                f"{extraction.merchant or 'Service'} price changing from "
                f"${extraction.old_price:.2f} to ${extraction.new_price:.2f}/mo"
            ),
            urgency="medium" if pct >= 20 else "low",
            deadline=extraction.renewal_date,
        ))
        cards.append(ActionCard(
            user_id=user_id,
            extraction_id=extraction.id,
            action_type="monitor_price",
            title="Monitor this price change",
            description=(
                f"Track whether {extraction.merchant or 'this service'} offers "
                f"promotional rates or discounts for existing subscribers"
            ),
            urgency="low",
        ))

    if extraction.warranty_end_date:
        days = days_until(extraction.warranty_end_date)
        if days is not None and 0 <= days <= 60:
            cards.append(ActionCard(
                user_id=user_id,
                extraction_id=extraction.id,
                action_type="warranty_reminder",
                title="Warranty expires soon",
                description=(
                    f"{extraction.merchant or 'Your'} warranty/coverage expires "
                    f"{human_time_description(days)}"
                ),
                urgency="high" if days <= 7 else "medium",
                deadline=extraction.warranty_end_date,
            ))

    if extraction.free_trial_end_date:
        days = days_until(extraction.free_trial_end_date)
        if days is not None and 0 <= days <= 14:
            amount_str = f" (${extraction.amount:.2f}/mo after)" if extraction.amount else ""
            cards.append(ActionCard(
                user_id=user_id,
                extraction_id=extraction.id,
                action_type="trial_ending_alert",
                title="Free trial ends soon",
                description=(
                    f"{extraction.merchant or 'Service'} trial ends "
                    f"{human_time_description(days)}{amount_str}"
                ),
                urgency="high" if days <= 2 else "medium",
                deadline=extraction.free_trial_end_date,
            ))

    if not cards:
        cards.append(ActionCard(
            user_id=user_id,
            extraction_id=extraction.id,
            action_type="no_action",
            title="No immediate action needed",
            description="No urgent deadlines or opportunities detected in this document.",
            urgency="low",
        ))

    for card in cards:
        db.add(card)
    db.commit()
    for card in cards:
        db.refresh(card)

    log_event(logger, logging.INFO, "action_cards_generated",
              user_id=user_id, extraction_id=extraction.id,
              card_count=len(cards),
              types=[c.action_type for c in cards],
              urgencies=[c.urgency for c in cards])

    return cards
