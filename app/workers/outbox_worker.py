import asyncio
import logging

import httpx

from app.clients.capashino import CapashinoClient
from app.config import settings
from app.database import async_session_maker
from app.repositories import OutboxRepository
from app.services import OutboxService

logger = logging.getLogger(__name__)


async def run_sync_outbox():
    """Бесконечный цикл, запускает синхронизацию раз 60 секунд"""
    while True:
        try:
            logger.info("Запуск фоновой синхронизации outbox...")
            async with async_session_maker() as db:
                async with httpx.AsyncClient(
                    base_url=settings.capashino_url,
                    headers = {"X-API-Key": settings.api_key},
                    timeout = httpx.Timeout(10, connect=5.0)
                    ) as raw_client:
                    
                    client = CapashinoClient(raw_client)
                    repo = OutboxRepository(db)
                    service = OutboxService(repo=repo, client=client)

                    await service.process_pending()
                    logger.info("Синхронизация outbox завершена")
        except Exception as e:
            logger.error("Ошибка в воркере outbox: %s", e, exc_info=True)

        await asyncio.sleep(60)



