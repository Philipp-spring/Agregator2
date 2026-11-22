import logging
import asyncio

from app.clients.capashino import CapashinoClient
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)

class OutboxService:
    def __init__(self, repo: OutboxRepository, client: CapashinoClient):
        self.repo = repo
        self.client = client

    async def process_pending(self):
        """Берет пачку записей из БД (таблицы outbox) и отправляет их в Capashino"""
        pending_records = await self.repo.get_pending(limit=1)

        if not pending_records:
            return 

        for record_id, payload in pending_records:
            try:
                await asyncio.sleep(0.5)
                await self.client.send_notification(
                        message=payload["message"],
                        reference_id=payload["ticket_id"],
                        idempotency_key=str(record_id)
                        )

                await self.repo.mark_as_sent(record_id)
                await self.repo.commit()
                logger.info("Уведомление %s успешно отправлено", record_id)

            except Exception as e:
                await self.repo.rollback()
                await self.repo.increment_attempts(record_id)
                logger.error("Ошибка при отправке %s: %r", record_id, e)
