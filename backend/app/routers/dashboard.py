from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import DashboardResponse
from app.services.dashboard import get_dashboard_data

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = get_dashboard_data(current_user.id, db)
    return DashboardResponse(**data)
