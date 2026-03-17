import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db, init_models, close_connections, rdb
from crud import create_link, get_link, delete_link, update_link
from models import Link

REDIS_LINK_PREFIX = "link:"
REDIS_TTL_SECONDS = int(timedelta(hours=24).total_seconds())


def get_cache_key(short_code: str) -> str:
    return f"{REDIS_LINK_PREFIX}{short_code}"


def serialize_link_for_cache(link: Link) -> str:
    return json.dumps(
        {
            "id": link.id,
            "original_url": link.original_url,
            "short_code": link.short_code,
            "click_count": link.click_count,
            "created_at": link.created_at.isoformat() if link.created_at else None,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "last_used_at": (
                link.last_used_at.isoformat() if link.last_used_at else None
            ),
            "is_anonymous": link.is_anonymous,
            "deleted_at": link.deleted_at.isoformat() if link.deleted_at else None,
        },
        default=str,
    )


def deserialize_link_from_cache(data: str) -> Optional[dict]:
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


class LinkCreate(BaseModel):
    original_url: str
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None


class LinkUpdate(BaseModel):
    new_url: str


class LinkResponse(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    is_anonymous: bool

    class Config:
        from_attributes = True


class LinkStatsResponse(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True


async def invalidate_link_cache(short_code: str):
    cache_key = get_cache_key(short_code)
    await rdb.delete(cache_key)


async def cache_link(link: Link):
    cache_key = get_cache_key(link.short_code)
    serialized = serialize_link_for_cache(link)
    await rdb.setex(cache_key, REDIS_TTL_SECONDS, serialized)


async def get_cached_link(short_code: str) -> Optional[dict]:
    cache_key = get_cache_key(short_code)
    cached = await rdb.get(cache_key)
    if cached:
        return deserialize_link_from_cache(cached)
    return None


async def increment_click_count_in_background(short_code: str, db: AsyncSession):
    try:
        await db.execute(
            update(Link)
            .where(Link.short_code == short_code, Link.deleted_at.is_(None))
            .values(
                click_count=Link.click_count + 1,
                last_used_at=datetime.utcnow(),
            )
        )
        await db.commit()

        result = await db.execute(
            select(Link).where(Link.short_code == short_code, Link.deleted_at.is_(None))
        )
        updated_link = result.scalar_one_or_none()
        if updated_link:
            await cache_link(updated_link)
    except Exception as e:
        print(f"⚠️ Failed to update click count for {short_code}: {e}")
        await db.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield
    await close_connections()


app = FastAPI(lifespan=lifespan, title="URL Shortener API")


@app.post("/links/shorten", response_model=LinkResponse, status_code=201)
async def create_short_link(body: LinkCreate, db: AsyncSession = Depends(get_db)):
    try:
        link = await create_link(
            original_url=body.original_url,
            custom_alias=body.custom_alias,
            expires_at=body.expires_at,
            user_id=None,
        )
        await cache_link(link)
        return link
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/links/{short_code}")
async def redirect_to_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    cached = await get_cached_link(short_code)

    if cached and not cached.get("deleted_at"):
        expires_at = cached.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    raise HTTPException(status_code=410, detail="Link has expired")
            except ValueError:
                pass

        asyncio.create_task(increment_click_count_in_background(short_code, db))

        return RedirectResponse(url=cached["original_url"])

    link = await get_link(short_code, db)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found or expired")

    await cache_link(link)

    asyncio.create_task(increment_click_count_in_background(short_code, db))

    return RedirectResponse(url=link.original_url)


@app.delete("/links/{short_code}")
async def delete_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    success = await delete_link(short_code, user_id=None, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")

    await invalidate_link_cache(short_code)

    return {"message": "Link deleted successfully"}


@app.put("/links/{short_code}", response_model=LinkResponse)
async def update_short_link(
    short_code: str, body: LinkUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        link = await update_link(
            short_code=short_code, new_url=body.new_url, user_id=None, db=db
        )
        await invalidate_link_cache(short_code)
        await cache_link(link)
        return link
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/links/{short_code}/stats", response_model=LinkStatsResponse)
async def get_stats_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    cached = await get_cached_link(short_code)

    if cached and not cached.get("deleted_at"):
        return LinkStatsResponse(
            short_code=cached["short_code"],
            original_url=cached["original_url"],
            click_count=cached["click_count"],
            created_at=datetime.fromisoformat(cached["created_at"])
            if cached.get("created_at")
            else datetime.utcnow(),
            last_used_at=(
                datetime.fromisoformat(cached["last_used_at"])
                if cached.get("last_used_at")
                else None
            ),
        )

    result = await db.execute(
        select(Link).where(Link.short_code == short_code, Link.deleted_at.is_(None))
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    return link


@app.get("/health")
async def health_check():
    """Проверка работоспособности приложения и соединений"""
    health = {"status": "ok", "services": {}}

    try:
        await rdb.ping()
        health["services"]["redis"] = "connected"
    except Exception as e:
        health["services"]["redis"] = f"error: {str(e)}"

    health["services"]["database"] = "configured"

    return health
