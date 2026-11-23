import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_key(self, key: str) -> IdempotencyKey | None:
        """Получение объектов ключ-идемпонтентности из БД"""
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
        return await self.db.scalar(stmt)

    async def create_key(self, key: str, request_hash: str, ticket_id: uuid.UUID) -> None:
        """Создание нового ключа идемпотентности"""
        new_key = IdempotencyKey(key=key, request_hash=request_hash, ticket_id=ticket_id)
        self.db.add(new_key)
        await self.db.flush()

    async def delete_key(self, key: str) -> None:
        """Удаление протухшего ключа из БД"""
        stmt = delete(IdempotencyKey).where(IdempotencyKey.key == key)
        await self.db.execute(stmt)
        await self.db.flush()
        

