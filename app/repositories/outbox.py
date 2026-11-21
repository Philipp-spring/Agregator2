import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Outbox


class OutboxRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_pending(self, limit: int = 10):
        """Получение ожидающих отправки записей"""
        stmt = (
            select(Outbox)
            .where(Outbox.status == "PENDING")
            .where(Outbox.attempts < 5)
            .limit(limit)
            )

        result = await self.db.scalars(stmt)
        return result.all()

    async def mark_as_sent(self, outbox_id: uuid.UUID):
        """Помечает записи как отправленные"""
        record = await self.db.get(Outbox, outbox_id)
        if record:
            record.status  = "SENT"
            await self.db.flush()


    async def increment_attempts(self, outbox_id: uuid.UUID):
        """Увеличивает счетчик неудачных попыток отправки"""
        record = await self.db.get(Outbox, outbox_id)
        if record:
            record.attempts += 1
            if record.attempts >= 5:
                record.status  = "FAILED"
        await self.db.flush()


    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()
