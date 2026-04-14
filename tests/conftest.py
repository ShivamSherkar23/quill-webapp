import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database as app_database
import app.deps as app_deps
from app.auth import create_session_token
from app.database import Base
from app.models import User
from main import app


@pytest_asyncio.fixture
async def db_session_factory(
    tmp_path, monkeypatch
) -> AsyncIterator[async_sessionmaker]:
    db_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(app_database, "engine", engine)
    monkeypatch.setattr(app_database, "async_session", session_factory)
    monkeypatch.setattr(app_deps, "async_session", session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield session_factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session_factory) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def create_user(db_session_factory):
    async def _create_user(
        username: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> User:
        from app.auth import hash_password

        async with db_session_factory() as session:
            user = User(
                username=username,
                email=email or f"{username}@example.com",
                display_name=display_name or username,
                hashed_password=hash_password("password123"),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create_user


@pytest_asyncio.fixture
async def login_as(client: AsyncClient):
    async def _login_as(user: User) -> AsyncClient:
        client.cookies.set("session", create_session_token(user.id))
        return client

    return _login_as
