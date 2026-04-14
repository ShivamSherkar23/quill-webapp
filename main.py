from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes.auth_routes import router as auth_router
from app.routes.auth_routes import templates as auth_templates
from app.routes.post_routes import router as post_router
from app.routes.post_routes import templates as post_templates
from app.routes.profile_routes import router as profile_router
from app.routes.profile_routes import templates as profile_templates


def time_ago(dt):
    if dt is None:
        return ""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}y ago"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register Jinja2 filter globally via each router's templates
for t in (post_templates, auth_templates, profile_templates):
    t.env.filters["time_ago"] = time_ago

app.include_router(auth_router)
app.include_router(post_router)
app.include_router(profile_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
