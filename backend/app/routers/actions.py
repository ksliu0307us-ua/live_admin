from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ActionCard, User
from app.schemas import ActionCardResponse, ActionCardUpdate

router = APIRouter(tags=["actions"])


@router.get("/actions")
def list_actions(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ActionCard).filter(ActionCard.user_id == current_user.id)
    if status:
        query = query.filter(ActionCard.status == status)
    cards = query.order_by(ActionCard.created_at.desc()).all()
    return [ActionCardResponse.model_validate(c) for c in cards]


@router.patch("/actions/{action_id}")
def update_action_card(
    action_id: str,
    update: ActionCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card = db.query(ActionCard).filter(
        ActionCard.id == action_id, ActionCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Action card not found")

    if update.status is not None:
        card.status = update.status.value
        if update.status.value == "completed" and not card.completed_at:
            card.completed_at = datetime.now(UTC)
    if update.reminder_date is not None:
        card.reminder_date = update.reminder_date
    if update.savings_amount is not None:
        card.savings_amount = update.savings_amount

    db.commit()
    db.refresh(card)
    return ActionCardResponse.model_validate(card)
