import random
import string
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Link
from database import AsyncSessionLocal, rdb


def generate_short_code(length: int = 7) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


async def link_exists(short_code: str) -> bool:
    return await rdb.exists(f"link:{short_code}")


async def create_link(
    original_url: str,
    custom_alias: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    user_id: Optional[uuid.UUID] = None,
) -> Link:
    async with AsyncSessionLocal() as db:
        if custom_alias:
            if not re.match(r"^[a-zA-Z0-9]{4,10}$", custom_alias):
                raise ValueError("Invalid alias format (4-10 alphanumeric chars)")

            if await link_exists(custom_alias):
                raise ValueError("Alias already exists")

            exists_in_db = await db.execute(
                select(Link).where(Link.short_code == custom_alias)
            )
            if exists_in_db.scalar_one_or_none():
                raise ValueError("Alias already exists in database")

            short_code = custom_alias
        else:
            while True:
                short_code = generate_short_code()
                if not await link_exists(short_code):
                    break

        link = Link(
            short_code=short_code,
            original_url=original_url,
            user_id=user_id,
            is_anonymous=user_id is None,
            expires_at=expires_at,
        )

        db.add(link)
        await db.commit()
        await db.refresh(link)

        ttl = 3600
        if expires_at and expires_at < datetime.now(timezone.utc):
            ttl = 60

        await rdb.setex(f"link:{link.short_code}", ttl, str(link.id))

        return link


async def get_link(short_code: str, db: AsyncSession) -> Optional[Link]:
    cached_id = await rdb.get(f"link:{short_code}")
    if cached_id:
        result = await db.execute(select(Link).where(Link.id == cached_id))
        link = result.scalar_one_or_none()
        if link:
            return link

    result = await db.execute(
        select(Link).where(
            Link.short_code == short_code,
            Link.deleted_at.is_(None),
            or_(
                Link.expires_at.is_(None), Link.expires_at > datetime.now(timezone.utc)
            ),
        )
    )
    link = result.scalar_one_or_none()

    if link:
        link.click_count += 1
        link.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        await rdb.setex(f"link:{short_code}", 3600, str(link.id))

    return link


async def delete_link(
    short_code: str,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[AsyncSession] = None,
) -> bool:
    local_db = False
    if not db:
        db = AsyncSessionLocal()
        local_db = True

    try:
        await rdb.delete(f"link:{short_code}")

        query = select(Link).where(
            Link.short_code == short_code, Link.deleted_at.is_(None)
        )

        if user_id:
            query = query.where(
                or_(
                    Link.user_id == user_id,
                    and_(Link.is_anonymous, Link.user_id.is_(None)),
                )
            )

        result = await db.execute(query)
        link = result.scalar_one_or_none()

        if link:
            link.deleted_at = datetime.now(timezone.utc)
            await db.commit()
            return True
        return False
    finally:
        if local_db:
            await db.close()


async def update_link(
    short_code: str,
    new_url: str,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[AsyncSession] = None,
) -> Link:
    local_db = False
    if not db:
        db = AsyncSessionLocal()
        local_db = True

    try:
        query = select(Link).where(
            Link.short_code == short_code, Link.deleted_at.is_(None)
        )
        if user_id:
            query = query.where(Link.user_id == user_id)

        result = await db.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            raise ValueError("Link not found")

        link.original_url = new_url
        await db.commit()

        await rdb.setex(f"link:{short_code}", 3600, str(link.id))

        return link
    finally:
        if local_db:
            await db.close()


async def search_links(
    original_url: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    db: Optional[AsyncSession] = None,
) -> List[Link]:
    local_db = False
    if not db:
        db = AsyncSessionLocal()
        local_db = True

    try:
        query = select(Link).where(
            Link.deleted_at.is_(None),
            or_(
                Link.expires_at.is_(None), Link.expires_at > datetime.now(timezone.utc)
            ),
        )

        if original_url:
            query = query.where(Link.original_url == original_url)

        if user_id:
            query = query.where(Link.user_id == user_id)

        result = await db.execute(query)
        return list(result.scalars().all())
    finally:
        if local_db:
            await db.close()
