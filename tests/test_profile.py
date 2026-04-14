from sqlalchemy import select

from app.models import Follow, User


async def test_follow_toggle_creates_and_removes_relationship(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    follower = await create_user("follower")
    target = await create_user("target")
    await login_as(follower)

    follow_response = await client.post(
        f"/profile/{target.username}/follow",
        follow_redirects=False,
    )
    assert follow_response.status_code == 303
    assert follow_response.headers["location"] == f"/profile/{target.username}"

    async with db_session_factory() as session:
        follow = await session.scalar(
            select(Follow).where(
                Follow.follower_id == follower.id,
                Follow.following_id == target.id,
            )
        )
    assert follow is not None

    unfollow_response = await client.post(
        f"/profile/{target.username}/follow",
        follow_redirects=False,
    )
    assert unfollow_response.status_code == 303

    async with db_session_factory() as session:
        follow = await session.scalar(
            select(Follow).where(
                Follow.follower_id == follower.id,
                Follow.following_id == target.id,
            )
        )
    assert follow is None


async def test_followers_and_following_pages_show_connected_users(
    client,
    create_user,
    login_as,
):
    follower = await create_user("follower", display_name="Follower")
    target = await create_user("target", display_name="Target")
    await login_as(follower)

    await client.post(f"/profile/{target.username}/follow", follow_redirects=False)

    followers_response = await client.get(f"/profile/{target.username}/followers")
    following_response = await client.get(f"/profile/{follower.username}/following")

    assert followers_response.status_code == 200
    assert "Follower" in followers_response.text
    assert "@follower" in followers_response.text

    assert following_response.status_code == 200
    assert "Target" in following_response.text
    assert "@target" in following_response.text


async def test_settings_update_persists_display_name_and_trimmed_bio(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    user = await create_user("alice", display_name="Old Name")
    await login_as(user)

    response = await client.post(
        "/settings",
        data={"display_name": "  New Name  ", "bio": "  Hello Quill  "},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/profile/{user.username}"

    async with db_session_factory() as session:
        refreshed_user = await session.scalar(select(User).where(User.id == user.id))

    assert refreshed_user is not None
    assert refreshed_user.display_name == "New Name"
    assert refreshed_user.bio == "Hello Quill"


async def test_delete_account_removes_user_and_clears_session_cookie(
    client,
    create_user,
    login_as,
    db_session_factory,
):
    user = await create_user("alice")
    await login_as(user)

    response = await client.post("/settings/delete-account", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/signup"
    assert 'session=""' in response.headers.get("set-cookie", "")

    async with db_session_factory() as session:
        deleted_user = await session.scalar(select(User).where(User.id == user.id))

    assert deleted_user is None
