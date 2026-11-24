import logging

from app.clients.capashino import CapashinoClient
from app.config import settings
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)

class OutboxService:
    def __init__(self, repo: OutboxRepository, client: CapashinoClient):
        self.repo = repo
        self.client = client

    async def process_pending(self):
        """Берет пачку записей из БД (таблицы outbox) и отправляет их в Capashino"""
        pending_records = await self.repo.get_pending(settings.outbox_batch_size)

        if not pending_records:
            return 

        for record_id, payload in pending_records:
            try:
                await self.client.send_notification(
                        idempotency_key=str(record_id),
                        message=payload["message"],
                        reference_id=payload["ticket_id"],
                        )

                await self.repo.mark_as_sent(record_id)
                await self.repo.commit()
                logger.info("Уведомление %s успешно отправлено", record_id)

            except Exception as e:
                await self.repo.rollback()
                await self.repo.increment_attempts(record_id)
                await self.repo.commit()
                logger.error("Ошибка при отправке %s: %r", record_id, e)
