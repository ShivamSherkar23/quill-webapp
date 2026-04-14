from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_session_token
from app.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/signup", response_class=HTMLResponse, tags=["Auth"])
async def signup_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(name="signup.html", request=request)


@router.post("/signup", tags=["Auth"])
async def signup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    # Check existing user
    existing = await db.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            name="signup.html",
            request=request,
            context={"error": "Username or email already taken"},
            status_code=400,
        )

    user = User(
        username=username,
        email=email,
        display_name=display_name or username,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session", create_session_token(user.id), httponly=True, samesite="lax"
    )
    return response


@router.get("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(name="login.html", request=request)


@router.post("/login", tags=["Auth"])
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            name="login.html",
            request=request,
            context={"error": "Invalid username or password"},
            status_code=400,
        )

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session", create_session_token(user.id), httponly=True, samesite="lax"
    )
    return response


@router.get("/logout", tags=["Auth"])
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response
