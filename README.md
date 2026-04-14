# Quill

A simple Twitter-like web app built with FastAPI. Supports user signup/login, posting (280-char limit), editing, deleting, likes, reposts, replies, follow/unfollow, search, user profiles, and dark mode.

## Features

- **Auth** — signup, login, logout with cookie-based sessions
- **Posts** — create, edit, delete (280-char limit with live counter)
- **Likes** — toggle like on any post, filled heart when liked
- **Reposts** — repost other users' posts
- **Replies** — threaded replies on post detail pages
- **Follow/Unfollow** — follow users, view followers/following lists
- **Feed** — "All" and "Following" tabs
- **Search** — text search across posts
- **Profiles** — display name, bio, post count, follower/following counts
- **Settings** — edit profile, delete account
- **Dark Mode** — system/light/dark toggle, persisted in localStorage

## Tech Stack

- **FastAPI** + **Uvicorn** — async web framework
- **SQLAlchemy** (async) + **PostgreSQL** — database
- **Jinja2** — server-side HTML templates
- **bcrypt** — password hashing
- **uv** — project/package manager

## Setup

```bash
# Install dependencies
uv sync

# Install dev dependencies for tests
uv sync --group dev

# Create the PostgreSQL database
createdb quill

# Run the app (uses postgresql://postgres:postgres@localhost:5432/quill by default)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or set a custom database URL
DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname" uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 in your browser.

## Tests

```bash
uv run --group dev pytest
```

## Taskfile

```bash
task install
task run
task lint
task test
task coverage
task check
```

## Lint

```bash
uv run --group dev ruff check --fix .
uv run --group dev ruff format .
uv run --group dev ruff check .
uv run --group dev ruff format --check .
```

## API Docs

Swagger UI is available at http://localhost:8000/docs with endpoints grouped under Auth, Posts, and Profile.
