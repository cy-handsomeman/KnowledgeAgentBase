from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from db.session import get_db
from models.user import User
from schemas.user import UserBrief

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserBrief])
def search_users(
    username: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keyword = username.strip()
    if len(keyword) < 2:
        return []

    return db.scalars(
        select(User)
        .where(User.username.like(f"{keyword}%"))
        .order_by(User.username)
        .limit(10)
    ).all()
