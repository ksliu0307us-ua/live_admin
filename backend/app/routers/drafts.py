import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import ActionCard, EmailDraft, User
from app.schemas import DraftRequest, EmailDraftResponse, EmailDraftUpdate
from app.services.draft_generator import generate_draft

logger = logging.getLogger(__name__)
router = APIRouter(tags=["drafts"])


@router.post("/actions/{action_id}/draft", status_code=201)
def create_draft(
    action_id: str,
    body: DraftRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card = db.query(ActionCard).filter(
        ActionCard.id == action_id, ActionCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Action card not found")
    tone = body.tone.value if body else "professional"
    try:
        draft = generate_draft(card, db, tone=tone, user_id=current_user.id)
        return EmailDraftResponse.model_validate(draft)
    except Exception as e:
        logger.exception("Draft generation failed")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "DRAFT_FAILED", "message": str(e), "details": {}}},
        )


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id, EmailDraft.user_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return EmailDraftResponse.model_validate(draft)


@router.patch("/drafts/{draft_id}")
def update_draft(
    draft_id: str,
    update: EmailDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    draft = db.query(EmailDraft).filter(
        EmailDraft.id == draft_id, EmailDraft.user_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if update.user_edited_body is not None:
        draft.user_edited_body = update.user_edited_body
    if update.copied is not None:
        draft.copied = update.copied
    db.commit()
    db.refresh(draft)
    return EmailDraftResponse.model_validate(draft)
