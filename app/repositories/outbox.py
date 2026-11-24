import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Outbox
from app.enums import OutboxStatus


class OutboxRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_pending(self, limit: int = 10):
        """Получение ожидающих отправки записей"""
        stmt = (
            select(Outbox.id, Outbox.payload)
            .where(Outbox.status == OutboxStatus.PENDING)
            .where(Outbox.attempts < settings.outbox_max_retries)
            .order_by(Outbox.created_at)
            .limit(limit)
            )

        result = await self.db.execute(stmt)
        return result.all()

    async def mark_as_sent(self, outbox_id: uuid.UUID):
        """Помечает записи как отправленные"""
        record = await self.db.get(Outbox, outbox_id)
        if record:
            record.status  = OutboxStatus.SENT
            await self.db.flush()


    async def increment_attempts(self, outbox_id: uuid.UUID):
        """Увеличивает счетчик неудачных попыток отправки"""
        record = await self.db.get(Outbox, outbox_id)
        if record:
            record.attempts += 1
            if record.attempts >= settings.outbox_max_retries:
                record.status  = OutboxStatus.FAILED
            await self.db.flush()


    async def commit(self):
        await self.db.commit()

    async def rollback(self):
        await self.db.rollback()
