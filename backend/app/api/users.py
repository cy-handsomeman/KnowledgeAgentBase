from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.ratelimit import user_rate_limit
from db.session import get_db
from models.user import User
from schemas.user import UserBrief

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserBrief],
    dependencies=[Depends(user_rate_limit(30, 60, "user-search"))],
)
def search_users(
    username: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keyword = username.strip()
    if len(keyword) < 2:
        return []

    # 转义 LIKE 通配符，避免用 "%"、"_" 绕过前缀匹配枚举用户。
    pattern = (
        keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return db.scalars(
        select(User)
        .where(User.username.like(f"{pattern}%", escape="\\"))
        .order_by(User.username)
        .limit(10)
    ).all()
