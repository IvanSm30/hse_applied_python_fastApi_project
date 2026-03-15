from sqlalchemy import select
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid

from database import get_db, close_connections
from crud import create_link, get_link, delete_link, update_link, search_links
from models import Link

app = FastAPI(
    title="URL Shortener API",
    description="Async URL Shortener with FastAPI, SQLAlchemy & Redis",
    version="1.0.0",
)


class LinkCreate(BaseModel):
    original_url: str = Field(..., description="Оригинальный URL")
    custom_alias: Optional[str] = Field(
        None, min_length=4, max_length=10, pattern=r"^[a-zA-Z0-9]+$"
    )
    expires_in_days: Optional[int] = Field(
        None, ge=1, le=365, description="Срок жизни в днях"
    )

    @validator("original_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class LinkResponse(BaseModel):
    id: uuid.UUID
    short_code: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int = 0
    is_anonymous: bool

    class Config:
        from_attributes = True


class LinkStats(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool


class LinkUpdate(BaseModel):
    original_url: str = Field(..., description="Новый оригинальный URL")

    @validator("original_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


@app.on_event("shutdown")
async def shutdown_event():
    await close_connections()


@app.post(
    "/links/shorten", response_model=LinkResponse, status_code=status.HTTP_201_CREATED
)
async def create_short_link(link_data: LinkCreate, db: AsyncSession = Depends(get_db)):
    expires_at = None
    if link_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=link_data.expires_in_days
        )

    try:
        link = await create_link(
            original_url=link_data.original_url,
            custom_alias=link_data.custom_alias,
            expires_at=expires_at,
            user_id=None,
        )
        return link
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@app.get("/links/{short_code}")
async def redirect_to_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    link = await get_link(short_code, db)

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found or expired"
        )

    return RedirectResponse(url=link.original_url, status_code=307)


@app.delete("/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    success = await delete_link(short_code, user_id=None, db=db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found or you don't have permission to delete it",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put("/links/{short_code}", response_model=LinkResponse)
async def update_short_link(
    short_code: str, link_data: LinkUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        link = await update_link(
            short_code=short_code, new_url=link_data.original_url, user_id=None, db=db
        )
        return link
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/links/{short_code}/stats", response_model=LinkStats)
async def get_stats_short_link(short_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Link).where(Link.short_code == short_code, Link.deleted_at.is_(None))
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link not found"
        )

    is_active = True
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        is_active = False

    return LinkStats(
        short_code=link.short_code,
        original_url=link.original_url,
        click_count=link.click_count,
        created_at=link.created_at,
        last_used_at=link.last_used_at,
        expires_at=link.expires_at,
        is_active=is_active,
    )


@app.get("/links/", response_model=List[LinkResponse])
async def list_links(db: AsyncSession = Depends(get_db)):
    links = await search_links(original_url=None, user_id=None, db=db)
    return links


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
