from fastapi import Request, HTTPException
from sqlalchemy import select

from app.auth import decode_session_token
from app.database import async_session
from app.models import User


async def get_current_user(request: Request) -> User | None:
    token = request.cookies.get("session")
    if not token:
        return None
    data = decode_session_token(token)
    if not data:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == data["user_id"]))
        return result.scalar_one_or_none()


async def require_login(request: Request) -> User:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
