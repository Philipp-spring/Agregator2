import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_key(self, key: str) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
        res = await self.db.scalars(stmt)
        return res.first()

    async def create(self, key: str, request_hash: str, ticket_id: uuid.UUID) -> None:
        new_key = IdempotencyKey(key=key, request_hash=request_hash, ticket_id=ticket_id)
        self.db.add(new_key)
        await self.db.flush()
