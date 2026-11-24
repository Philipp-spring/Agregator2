import uuid
from unittest.mock import AsyncMock

import pytest

from app.clients.capashino import CapashinoClient
from app.repositories.outbox import OutboxRepository
from app.services.outbox import OutboxService


@pytest.mark.asyncio
async def test_outbox_process_pending_success():
    """Тест: воркер успешно отправляет уведомление и помечает запись отправленной"""
    mock_repo = AsyncMock(spec=OutboxRepository)
    mock_client = AsyncMock(spec=CapashinoClient)
    record_id = uuid.uuid4()

    mock_repo.get_pending.return_value = [(record_id, {"message": "Ваш билет оформлен", "ticket_id": "ticket-123"})]

    service = OutboxService(repo=mock_repo, client=mock_client)
    await service.process_pending()

    mock_client.send_notification.assert_awaited_once_with(
        message="Ваш билет оформлен",
        reference_id="ticket-123",
        idempotency_key=str(record_id),
            )

    mock_repo.mark_as_sent.assert_awaited_once_with(record_id)
    mock_repo.commit.assert_awaited_once()
    mock_repo.rollback.assert_not_awaited()



@pytest.mark.asyncio
async def test_outbox_process_pending_error_increments_attempts():
    """Тест: при ошибке отправки воркер делает rollback, увеличивает счетчик попыток и не падает."""
    mock_repo = AsyncMock(spec=OutboxRepository)
    mock_client = AsyncMock(spec=CapashinoClient)
    record_id = uuid.uuid4()

    mock_repo.get_pending.return_value =  [(record_id, {"message": "Ваш билет оформлен", "ticket_id": "ticket-123"})] 
    mock_client.send_notification.side_effect = Exception("Ошибка")

    service = OutboxService(repo=mock_repo, client=mock_client)
    await service.process_pending()

    mock_client.send_notification.assert_awaited_once()
    mock_repo.mark_as_sent.assert_not_awaited()
    mock_repo.rollback.assert_awaited_once()
    mock_repo.increment_attempts.assert_awaited_once_with(record_id)
    mock_repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_outbox_process_pending_empty():
    """Тест: если новых записей в outbox нет, клиент не вызывается."""
    mock_repo = AsyncMock(spec=OutboxRepository)
    mock_client = AsyncMock(spec=CapashinoClient)

    mock_repo.get_pending.return_value = []

    service = OutboxService(repo=mock_repo, client=mock_client)
    await service.process_pending()

    mock_client.send_notification.assert_not_awaited()
    mock_repo.mark_as_sent.assert_not_awaited()
    mock_repo.rollback.assert_not_awaited()
    mock_repo.commit.assert_not_awaited()
    
