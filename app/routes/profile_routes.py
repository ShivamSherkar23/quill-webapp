from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Post, Follow, Repost
from app.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/profile/{username}", response_class=HTMLResponse, tags=["Profile"])
async def view_profile(
    username: str, request: Request, db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.username == username))
    profile_user = result.scalar_one_or_none()

    if not profile_user:
        return templates.TemplateResponse(
            name="404.html",
            request=request,
            context={"user": current_user},
            status_code=404,
        )

    posts_result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .where(Post.user_id == profile_user.id, Post.parent_id.is_(None))
        .order_by(Post.created_at.desc())
    )
    reposts_result = await db.execute(
        select(Repost)
        .options(
            selectinload(Repost.user),
            selectinload(Repost.post).selectinload(Post.author),
        )
        .join(Post, Repost.post_id == Post.id)
        .where(Repost.user_id == profile_user.id, Post.parent_id.is_(None))
        .order_by(Repost.created_at.desc())
    )

    # Enrich timeline items with counts
    from app.routes.post_routes import _build_timeline, _enrich_posts

    posts = _build_timeline(
        posts_result.scalars().all(), reposts_result.scalars().all()
    )
    posts = await _enrich_posts(posts, current_user, db)

    # Follower/following counts
    post_count = (
        await db.execute(
            select(func.count()).where(
                Post.user_id == profile_user.id, Post.parent_id.is_(None)
            )
        )
    ).scalar()
    follower_count = (
        await db.execute(
            select(func.count()).where(Follow.following_id == profile_user.id)
        )
    ).scalar()
    following_count = (
        await db.execute(
            select(func.count()).where(Follow.follower_id == profile_user.id)
        )
    ).scalar()
    repost_count = (
        await db.execute(select(func.count()).where(Repost.user_id == profile_user.id))
    ).scalar()

    # Does current user follow this profile?
    is_following = False
    if current_user.id != profile_user.id:
        f = await db.execute(
            select(Follow).where(
                Follow.follower_id == current_user.id,
                Follow.following_id == profile_user.id,
            )
        )
        is_following = f.scalar_one_or_none() is not None

    return templates.TemplateResponse(
        name="profile.html",
        request=request,
        context={
            "user": current_user,
            "profile_user": profile_user,
            "posts": posts,
            "is_own": current_user.id == profile_user.id,
            "is_following": is_following,
            "post_count": post_count,
            "repost_count": repost_count,
            "follower_count": follower_count,
            "following_count": following_count,
        },
    )


@router.post("/profile/{username}/follow", tags=["Follow"])
async def toggle_follow(
    username: str, request: Request, db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()

    if not target or target.id == current_user.id:
        return RedirectResponse(f"/profile/{username}", status_code=303)

    existing = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.following_id == target.id,
        )
    )
    follow = existing.scalar_one_or_none()
    if follow:
        await db.delete(follow)
    else:
        db.add(Follow(follower_id=current_user.id, following_id=target.id))
    await db.commit()

    return RedirectResponse(f"/profile/{username}", status_code=303)


@router.get(
    "/profile/{username}/followers", response_class=HTMLResponse, tags=["Follow"]
)
async def followers_list(
    username: str, request: Request, db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.username == username))
    profile_user = result.scalar_one_or_none()
    if not profile_user:
        return templates.TemplateResponse(
            name="404.html",
            request=request,
            context={"user": current_user},
            status_code=404,
        )

    followers_result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == profile_user.id)
    )
    users = followers_result.scalars().all()

    return templates.TemplateResponse(
        name="user_list.html",
        request=request,
        context={
            "user": current_user,
            "profile_user": profile_user,
            "users": users,
            "title": "Followers",
        },
    )


@router.get(
    "/profile/{username}/following", response_class=HTMLResponse, tags=["Follow"]
)
async def following_list(
    username: str, request: Request, db: AsyncSession = Depends(get_db)
):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.username == username))
    profile_user = result.scalar_one_or_none()
    if not profile_user:
        return templates.TemplateResponse(
            name="404.html",
            request=request,
            context={"user": current_user},
            status_code=404,
        )

    following_result = await db.execute(
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == profile_user.id)
    )
    users = following_result.scalars().all()

    return templates.TemplateResponse(
        name="user_list.html",
        request=request,
        context={
            "user": current_user,
            "profile_user": profile_user,
            "users": users,
            "title": "Following",
        },
    )


@router.get("/settings", response_class=HTMLResponse, tags=["Settings"])
async def settings_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        name="settings.html", request=request, context={"user": user}
    )


@router.post("/settings", tags=["Settings"])
async def update_settings(
    request: Request,
    display_name: str = Form(""),
    bio: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()

    db_user.display_name = display_name.strip() or db_user.username
    db_user.bio = bio.strip()[:500]
    await db.commit()

    return RedirectResponse(f"/profile/{db_user.username}", status_code=303)


@router.post("/settings/delete-account", tags=["Settings"])
async def delete_account(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()

    await db.delete(db_user)
    await db.commit()

    response = RedirectResponse("/signup", status_code=303)
    response.delete_cookie("session")
    return response
