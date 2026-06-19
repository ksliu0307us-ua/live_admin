"""Dashboard aggregation service."""

from datetime import datetime

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import ActionCard, Extraction


def get_dashboard_data(user_id: str, db: Session) -> dict:
    total_savings = db.query(func.coalesce(func.sum(ActionCard.savings_amount), 0.0)).filter(
        ActionCard.user_id == user_id,
        ActionCard.status == "completed",
    ).scalar() or 0.0

    documents_count = db.query(func.count(Extraction.id)).filter(
        Extraction.user_id == user_id,
    ).scalar() or 0

    status_counts = db.query(
        ActionCard.status, func.count(ActionCard.id)
    ).filter(
        ActionCard.user_id == user_id,
    ).group_by(ActionCard.status).all()

    actions_by_status = {s: c for s, c in status_counts}
    completed_actions = actions_by_status.get("completed", 0)

    monthly_rows = db.query(
        extract("year", ActionCard.completed_at).label("year"),
        extract("month", ActionCard.completed_at).label("month"),
        func.coalesce(func.sum(ActionCard.savings_amount), 0.0).label("amount"),
        func.count(ActionCard.id).label("count"),
    ).filter(
        ActionCard.user_id == user_id,
        ActionCard.status == "completed",
        ActionCard.completed_at.isnot(None),
    ).group_by("year", "month").order_by("year", "month").all()

    monthly_savings = []
    for row in monthly_rows:
        y, m = int(row.year), int(row.month)
        monthly_savings.append({
            "month": f"{y}-{m:02d}",
            "amount": float(row.amount),
            "count": int(row.count),
        })

    return {
        "total_savings": float(total_savings),
        "documents_count": documents_count,
        "actions_by_status": actions_by_status,
        "completed_actions": completed_actions,
        "monthly_savings": monthly_savings,
    }
