import json
import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Extraction, User
from app.schemas import (
    ActionCardResponse,
    ExtractionListItem,
    ExtractionRequest,
    ExtractionResponse,
    ExtractionWithActions,
    PaginatedDocuments,
)
from app.services.extraction import run_extraction

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])
limiter = Limiter(key_func=get_remote_address)


def _extraction_to_response(extraction: Extraction) -> ExtractionResponse:
    field_confs = None
    if extraction.field_confidences:
        try:
            field_confs = json.loads(extraction.field_confidences)
        except (json.JSONDecodeError, TypeError):
            field_confs = None

    return ExtractionResponse(
        id=extraction.id,
        merchant=extraction.merchant,
        document_type=extraction.document_type,
        amount=extraction.amount,
        currency=extraction.currency,
        purchase_date=extraction.purchase_date,
        subscription_status=extraction.subscription_status,
        renewal_date=extraction.renewal_date,
        free_trial_end_date=extraction.free_trial_end_date,
        return_deadline=extraction.return_deadline,
        cancellation_deadline=extraction.cancellation_deadline,
        warranty_end_date=extraction.warranty_end_date,
        cancellation_policy=extraction.cancellation_policy,
        refund_opportunity=extraction.refund_opportunity,
        price_increased=extraction.price_increased,
        old_price=extraction.old_price,
        new_price=extraction.new_price,
        detected_risk=extraction.detected_risk,
        recommended_action=extraction.recommended_action,
        explanation=extraction.explanation,
        confidence_score=extraction.confidence_score,
        field_confidences=field_confs,
        is_duplicate=extraction.is_duplicate,
        input_type=extraction.input_type,
        created_at=extraction.created_at,
    )


@router.post("/extract", status_code=201)
@limiter.limit("100/hour")
def create_extraction(
    request: Request,
    req: ExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        from app.services.action_engine import generate_action_cards

        extraction = run_extraction(req.input_text, req.input_type, db, user_id=current_user.id)
        action_cards = generate_action_cards(extraction, db, user_id=current_user.id)

        return ExtractionWithActions(
            extraction=_extraction_to_response(extraction),
            action_cards=[ActionCardResponse.model_validate(ac) for ac in action_cards],
        )
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "EXTRACTION_FAILED", "message": str(e), "details": {}}},
        )


@router.post("/extract/file", status_code=201)
@limiter.limit("100/hour")
async def create_extraction_from_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.size and file.size > 500_000:
        raise HTTPException(status_code=413, detail="File too large (max 500KB)")

    allowed = {".txt", ".eml", ".text"}
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    try:
        from app.services.action_engine import generate_action_cards

        extraction = run_extraction(text, "file_upload", db, user_id=current_user.id)
        action_cards = generate_action_cards(extraction, db, user_id=current_user.id)

        return ExtractionWithActions(
            extraction=_extraction_to_response(extraction),
            action_cards=[ActionCardResponse.model_validate(ac) for ac in action_cards],
        )
    except Exception as e:
        logger.exception("File extraction failed")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "EXTRACTION_FAILED", "message": str(e), "details": {}}},
        )


@router.get("/documents")
def list_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    document_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Extraction).filter(Extraction.user_id == current_user.id)
    if document_type:
        query = query.filter(Extraction.document_type == document_type)

    total = query.count()
    pages = math.ceil(total / per_page) if total > 0 else 1
    extractions = query.order_by(Extraction.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    items = [
        ExtractionListItem(
            id=ex.id,
            merchant=ex.merchant,
            document_type=ex.document_type,
            amount=ex.amount,
            currency=ex.currency,
            confidence_score=ex.confidence_score,
            input_type=ex.input_type,
            created_at=ex.created_at,
            action_count=len(ex.action_cards),
        )
        for ex in extractions
    ]
    return PaginatedDocuments(items=items, total=total, page=page, per_page=per_page, pages=pages)


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    extraction = db.query(Extraction).filter(
        Extraction.id == document_id, Extraction.user_id == current_user.id
    ).first()
    if not extraction:
        raise HTTPException(status_code=404, detail="Document not found")
    return ExtractionWithActions(
        extraction=_extraction_to_response(extraction),
        action_cards=[ActionCardResponse.model_validate(ac) for ac in extraction.action_cards],
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    extraction = db.query(Extraction).filter(
        Extraction.id == document_id, Extraction.user_id == current_user.id
    ).first()
    if not extraction:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(extraction)
    db.commit()
