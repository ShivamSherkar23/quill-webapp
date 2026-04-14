from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Post, Like, Repost, Follow
from app.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class TimelinePost:
    def __init__(self, post: Post, *, timeline_created_at=None, reposted_by_name=None):
        self._post = post
        self.timeline_created_at = timeline_created_at or post.created_at
        self.reposted_by_name = reposted_by_name

    def __getattr__(self, item):
        return getattr(self._post, item)


def _wrap_posts(posts):
    return [TimelinePost(post, timeline_created_at=post.created_at) for post in posts]


def _build_timeline(posts, reposts):
    timeline = _wrap_posts(posts)
    timeline.extend(
        TimelinePost(
            repost.post,
            timeline_created_at=repost.created_at,
            reposted_by_name=repost.user.display_name or repost.user.username,
        )
        for repost in reposts
    )
    timeline.sort(key=lambda item: item.timeline_created_at, reverse=True)
    return timeline[:50]


async def _enrich_posts(posts, user, db):
    """Add like_count, repost_count, reply_count, liked_by_me, reposted_by_me to each post."""
    if not posts:
        return posts
    post_ids = [p.id for p in posts]

    # Like counts
    like_counts = dict(
        (
            await db.execute(
                select(Like.post_id, func.count())
                .where(Like.post_id.in_(post_ids))
                .group_by(Like.post_id)
            )
        ).all()
    )
    # Repost counts
    repost_counts = dict(
        (
            await db.execute(
                select(Repost.post_id, func.count())
                .where(Repost.post_id.in_(post_ids))
                .group_by(Repost.post_id)
            )
        ).all()
    )
    # Reply counts
    reply_counts = dict(
        (
            await db.execute(
                select(Post.parent_id, func.count())
                .where(Post.parent_id.in_(post_ids))
                .group_by(Post.parent_id)
            )
        ).all()
    )
    # User's likes
    my_likes = set(
        r[0]
        for r in (
            await db.execute(
                select(Like.post_id).where(
                    Like.user_id == user.id, Like.post_id.in_(post_ids)
                )
            )
        ).all()
    )
    # User's reposts
    my_reposts = set(
        r[0]
        for r in (
            await db.execute(
                select(Repost.post_id).where(
                    Repost.user_id == user.id, Repost.post_id.in_(post_ids)
                )
            )
        ).all()
    )

    for post in posts:
        post.like_count = like_counts.get(post.id, 0)
        post.repost_count = repost_counts.get(post.id, 0)
        post.reply_count = reply_counts.get(post.id, 0)
        post.liked_by_me = post.id in my_likes
        post.reposted_by_me = post.id in my_reposts

    return posts


@router.get("/", response_class=HTMLResponse, tags=["Feed"])
async def feed(
    request: Request, tab: str = Query("all"), db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if tab == "following":
        visible_user_ids = [
            r[0]
            for r in (
                await db.execute(
                    select(Follow.following_id).where(Follow.follower_id == user.id)
                )
            ).all()
        ]
        visible_user_ids.append(user.id)
        post_query = select(Post).where(
            Post.user_id.in_(visible_user_ids), Post.parent_id.is_(None)
        )
        repost_query = select(Repost).where(Repost.user_id.in_(visible_user_ids))
    else:
        post_query = select(Post).where(Post.parent_id.is_(None))
        repost_query = select(Repost)

    post_result = await db.execute(
        post_query.options(selectinload(Post.author))
        .order_by(Post.created_at.desc())
        .limit(50)
    )
    repost_result = await db.execute(
        repost_query.options(
            selectinload(Repost.user),
            selectinload(Repost.post).selectinload(Post.author),
        )
        .join(Post, Repost.post_id == Post.id)
        .where(Post.parent_id.is_(None))
        .order_by(Repost.created_at.desc())
        .limit(50)
    )
    posts = _build_timeline(post_result.scalars().all(), repost_result.scalars().all())
    posts = await _enrich_posts(posts, user, db)

    return templates.TemplateResponse(
        name="feed.html",
        request=request,
        context={"user": user, "posts": posts, "tab": tab},
    )


@router.get("/search", response_class=HTMLResponse, tags=["Search"])
async def search_posts(
    request: Request, q: str = Query(""), db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    posts = []
    if q.strip():
        result = await db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.content.ilike(f"%{q.strip()}%"), Post.parent_id.is_(None))
            .order_by(Post.created_at.desc())
            .limit(50)
        )
        posts = result.scalars().all()
        posts = await _enrich_posts(posts, user, db)

    return templates.TemplateResponse(
        name="search.html",
        request=request,
        context={"user": user, "posts": posts, "query": q},
    )


@router.post("/posts", tags=["Posts"])
async def create_post(
    request: Request,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if len(content.strip()) == 0 or len(content) > 280:
        return RedirectResponse("/", status_code=303)

    post = Post(content=content.strip(), user_id=user.id)
    db.add(post)
    await db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/posts/{post_id}", response_class=HTMLResponse, tags=["Posts"])
async def post_detail(
    post_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(
        select(Post).options(selectinload(Post.author)).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        return templates.TemplateResponse(
            name="404.html", request=request, context={"user": user}, status_code=404
        )

    await _enrich_posts([post], user, db)

    # Load replies
    replies_result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))
        .where(Post.parent_id == post_id)
        .order_by(Post.created_at.asc())
    )
    replies = replies_result.scalars().all()
    replies = await _enrich_posts(replies, user, db)

    return templates.TemplateResponse(
        name="post_detail.html",
        request=request,
        context={"user": user, "post": post, "replies": replies},
    )


@router.post("/posts/{post_id}/reply", tags=["Replies"])
async def reply_to_post(
    post_id: int,
    request: Request,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(Post).where(Post.id == post_id))
    parent = result.scalar_one_or_none()
    if not parent:
        return RedirectResponse("/", status_code=303)

    if len(content.strip()) == 0 or len(content) > 280:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    reply = Post(content=content.strip(), user_id=user.id, parent_id=post_id)
    db.add(reply)
    await db.commit()
    return RedirectResponse(f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/like", tags=["Likes"])
async def toggle_like(
    post_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(
        select(Like).where(Like.user_id == user.id, Like.post_id == post_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
    else:
        db.add(Like(user_id=user.id, post_id=post_id))
    await db.commit()

    referer = request.headers.get("referer", "/")
    return RedirectResponse(referer, status_code=303)


@router.post("/posts/{post_id}/repost", tags=["Reposts"])
async def toggle_repost(
    post_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Can't repost your own post
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if not post or post.user_id == user.id:
        referer = request.headers.get("referer", "/")
        return RedirectResponse(referer, status_code=303)

    result = await db.execute(
        select(Repost).where(Repost.user_id == user.id, Repost.post_id == post_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
    else:
        db.add(Repost(user_id=user.id, post_id=post_id))
    await db.commit()

    referer = request.headers.get("referer", "/")
    return RedirectResponse(referer, status_code=303)


@router.get("/posts/{post_id}/edit", response_class=HTMLResponse, tags=["Posts"])
async def edit_post_page(
    post_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if not post or post.user_id != user.id:
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        name="edit_post.html", request=request, context={"user": user, "post": post}
    )


@router.post("/posts/{post_id}/edit", tags=["Posts"])
async def edit_post(
    post_id: int,
    request: Request,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if not post or post.user_id != user.id:
        return RedirectResponse("/", status_code=303)

    if len(content.strip()) == 0 or len(content) > 280:
        return templates.TemplateResponse(
            name="edit_post.html",
            request=request,
            context={
                "user": user,
                "post": post,
                "error": "Content must be 1-280 characters",
            },
            status_code=400,
        )

    post.content = content.strip()
    await db.commit()
    return RedirectResponse("/", status_code=303)


@router.post("/posts/{post_id}/delete", tags=["Posts"])
async def delete_post(
    post_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()

    if not post or post.user_id != user.id:
        return RedirectResponse("/", status_code=303)

    await db.delete(post)
    await db.commit()
    return RedirectResponse("/", status_code=303)
