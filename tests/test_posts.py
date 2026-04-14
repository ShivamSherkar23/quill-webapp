from sqlalchemy import select

from app.models import Like, Post


async def test_create_post_persists_trimmed_content(
    client, create_user, login_as, db_session_factory
):
    user = await create_user("alice")
    await login_as(user)

    response = await client.post(
        "/posts",
        data={"content": "  hello quill  "},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    async with db_session_factory() as session:
        post = await session.scalar(select(Post).where(Post.user_id == user.id))

    assert post is not None
    assert post.content == "hello quill"


async def test_feed_shows_you_reposted_badge_for_reposted_posts(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    author = await create_user("author", display_name="Author")
    reposter = await create_user("reposter", display_name="Reposter")

    async with db_session_factory() as session:
        post = Post(content="Original post", user_id=author.id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

    await login_as(reposter)
    repost_response = await client.post(
        f"/posts/{post_id}/repost",
        headers={"referer": "/"},
        follow_redirects=False,
    )

    assert repost_response.status_code == 303

    feed_response = await client.get("/")

    assert feed_response.status_code == 200
    assert "You reposted" in feed_response.text
    assert "Author" in feed_response.text
    assert "@author" in feed_response.text
    assert "Original post" in feed_response.text


async def test_toggle_like_persists_and_renders_count(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    author = await create_user("author")
    liker = await create_user("liker")

    async with db_session_factory() as session:
        post = Post(content="Likeable post", user_id=author.id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

    await login_as(liker)
    response = await client.post(
        f"/posts/{post_id}/like",
        headers={"referer": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    async with db_session_factory() as session:
        like = await session.scalar(
            select(Like).where(Like.user_id == liker.id, Like.post_id == post_id)
        )

    assert like is not None

    feed_response = await client.get("/")
    assert "Likeable post" in feed_response.text
    assert "> 1</button>" in feed_response.text or " 1</button>" in feed_response.text


async def test_reply_creates_child_post_and_shows_on_detail_page(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    author = await create_user("author")
    replier = await create_user("replier")

    async with db_session_factory() as session:
        post = Post(content="Parent post", user_id=author.id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

    await login_as(replier)
    response = await client.post(
        f"/posts/{post_id}/reply",
        data={"content": "  first reply  "},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/posts/{post_id}"

    async with db_session_factory() as session:
        reply = await session.scalar(select(Post).where(Post.parent_id == post_id))

    assert reply is not None
    assert reply.content == "first reply"
    assert reply.user_id == replier.id

    detail_response = await client.get(f"/posts/{post_id}")
    assert "Parent post" in detail_response.text
    assert "first reply" in detail_response.text


async def test_profile_shows_reposted_items_with_original_author(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    author = await create_user("author", display_name="Author")
    reposter = await create_user("reposter", display_name="Reposter")

    async with db_session_factory() as session:
        post = Post(content="Profile repost", user_id=author.id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

    await login_as(reposter)
    await client.post(
        f"/posts/{post_id}/repost",
        headers={"referer": f"/profile/{reposter.username}"},
        follow_redirects=False,
    )

    profile_response = await client.get(f"/profile/{reposter.username}")

    assert profile_response.status_code == 200
    assert "You reposted" in profile_response.text
    assert "Author" in profile_response.text
    assert "@author" in profile_response.text
    assert "Profile repost" in profile_response.text


async def test_user_cannot_repost_their_own_post(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    author = await create_user("author", display_name="Author")

    async with db_session_factory() as session:
        post = Post(content="My own post", user_id=author.id)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        post_id = post.id

    await login_as(author)
    response = await client.post(
        f"/posts/{post_id}/repost",
        headers={"referer": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    feed_response = await client.get("/")

    assert "You reposted" not in feed_response.text
