from sqlalchemy import select

from app.models import User


async def test_signup_creates_user_and_session_cookie(client, db_session_factory):
    response = await client.post(
        "/signup",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
            "display_name": "Alice",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers.get("set-cookie", "")

    async with db_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "alice"))

    assert user is not None
    assert user.display_name == "Alice"


async def test_login_rejects_invalid_password(client, create_user):
    await create_user("alice")

    response = await client.post(
        "/login",
        data={"username": "alice", "password": "wrong-password"},
    )

    assert response.status_code == 400
    assert "Invalid username or password" in response.text
