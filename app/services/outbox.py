import logging

from app.clients.capashino import CapashinoClient
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)

class OutboxService:
    def __init__(self, repo: OutboxRepository, client: CapashinoClient):
        self.repo = repo
        self.client = client

    async def process_pending(self):
        """Берет пачку записей из БД (таблицы outbox) и отправляет их в Capashino"""
        pending_records = await self.repo.get_pending(limit=10)

        if not pending_records:
            return 

        for record in pending_records:
            record_id = record.id
            try:
                await self.client.send_notification(
                        message=record.payload["message"],
                        reference_id=record.payload["ticket_id"],
                        idempotency_key=str(record_id)
                        )

                await self.repo.mark_as_sent(record_id)
                await self.repo.commit()
                logger.info("Уведомление %s успешно отправлено", record_id)

            except Exception as e:
                await self.repo.rollback()
                await self.repo.increment_attempts(record_id)
                logger.error("Ошибка при отправке %s: %s", record_id, e)
