import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from app.clients.provider import EventsProviderClient
from app.config import settings
from app.exceptions import IdempotencyConflictError
from app.models import Event
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.tickets import SQLAlchemyTicketRepository
from app.services.tickets import TicketService


def _make_mock_event(
            event_id: uuid.UUID | None = None, 
            status: str = "published",
            registration_deadline: datetime | None = None,
            **kwargs,
            ) -> Event:
    """Вспомогательная функция для создания валидного опубликованного события."""
    now = datetime.now(UTC)
    data = {
        "id": event_id or uuid.uuid4(),
        "name": "Тестовое событие",
        "status": status,
        "registration_deadline": registration_deadline or (now + timedelta(days=1)),
        "event_time": now + timedelta(days=2),
        "place_id": uuid.uuid4(),
        "number_of_visitors": 0,
        "changed_at": now,
    }
    data.update(kwargs)
    return Event(**data)


@pytest.mark.asyncio
async def test_idempotency_first_request_saves_key():
    """Тест: первый запрос с idempotency_key создает билет и сохраняет ключ в БД"""
    mock_repo = AsyncMock(spec=SQLAlchemyTicketRepository)
    mock_client = AsyncMock(spec=EventsProviderClient)
    mock_idem_repo = AsyncMock(spec=IdempotencyRepository)

    mock_idem_repo.get_key.return_value = None

    event_id = uuid.uuid4()
    new_ticket_id = uuid.uuid4()
    key_id = uuid.uuid4()
    mock_repo.get_event.return_value = _make_mock_event(event_id)
    mock_client.get_seats.return_value = {"seats": ["A1"]}
    mock_client.register.return_value = {"ticket_id": str(new_ticket_id)}

    service = TicketService(client=mock_client, repo=mock_repo, idem_repo=mock_idem_repo)

    result = await service.create_ticket(
            event_id=event_id, 
            first_name="Иван",
            last_name="Иванов",
            email="ivan@example.com",
            seat="A1",
            idempotency_key=str(key_id),
            )

    assert result == str(new_ticket_id)
    mock_idem_repo.create_key.assert_awaited_once()
    mock_repo.commit.assert_awaited_once()



@pytest.mark.asyncio
async def test_idempotency_duplicate_request_returns_existing_ticket():
    """Тест: повторный запрос с тем же ключом и данными возвращает старый ticket_id без вызова API."""
    mock_repo = AsyncMock(spec=SQLAlchemyTicketRepository)
    mock_client = AsyncMock(spec=EventsProviderClient)
    mock_idem_repo = AsyncMock(spec=IdempotencyRepository)

    service = TicketService(client=mock_client, repo=mock_repo, idem_repo=mock_idem_repo)

    key_id = uuid.uuid4()
    event_id = uuid.uuid4()
    existing_ticket_id = uuid.uuid4()
    expected_hash = service._calculate_hash(
        event_id, "Иван", "Иванов", "ivan@example.com", "A1"
    )


    mock_idem_repo.get_key.return_value = Mock(
            created_at=datetime.now(UTC) - timedelta(seconds=10),
            request_hash=expected_hash,
            ticket_id=existing_ticket_id,
            )

    result = await service.create_ticket(
        event_id=event_id,
        first_name="Иван",
        last_name="Иванов",
        email="ivan@example.com",
        seat="A1",
        idempotency_key=str(key_id),
    )

    assert result == str(existing_ticket_id)
    mock_client.register.assert_not_awaited()
    mock_repo.create.assert_not_awaited()







@pytest.mark.asyncio
async def test_idempotency_conflict_raises_error():
    """Тест: тот же ключ с другими данными выбрасывает IdempotencyConflictError."""
    mock_repo = AsyncMock(spec=SQLAlchemyTicketRepository)
    mock_client = AsyncMock(spec=EventsProviderClient)
    mock_idem_repo = AsyncMock(spec=IdempotencyRepository)

    service = TicketService(client=mock_client, repo=mock_repo, idem_repo=mock_idem_repo)

    key_id = uuid.uuid4()
    event_id = uuid.uuid4()
    old_hash = service._calculate_hash(
        event_id, "Иван", "Иванов", "ivan@example.com", "A1"
    )

    mock_idem_repo.get_key.return_value = Mock(
        created_at=datetime.now(UTC) - timedelta(seconds=10),
        request_hash=old_hash,
        ticket_id=uuid.uuid4(),
    )

    with pytest.raises(IdempotencyConflictError):
        await service.create_ticket(
            event_id=event_id,
            first_name="Иван",
            last_name="Иванов",
            email="ivan@example.com",
            seat="B2",
            idempotency_key=str(key_id),
        )

    mock_client.register.assert_not_awaited()
    mock_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_idempotency_expired_key_recreates_ticket():
    """Тест: если TTL ключа истек, старый ключ удаляется и создается новый билет."""
    mock_repo = AsyncMock(spec=SQLAlchemyTicketRepository)
    mock_client = AsyncMock(spec=EventsProviderClient)
    mock_idem_repo = AsyncMock(spec=IdempotencyRepository)

    event_id = uuid.uuid4()
    new_ticket_id = uuid.uuid4()
    key_id = uuid.uuid4()

    expired_time = datetime.now(UTC) - timedelta(seconds=settings.idempotency_ttl_seconds + 60)
    mock_idem_repo.get_key.return_value = Mock(
        created_at=expired_time,
        request_hash="any-old-hash",
        ticket_id=uuid.uuid4(),
    )

    mock_repo.get_event.return_value = _make_mock_event(event_id)
    mock_client.get_seats.return_value = {"seats": ["A1"]}
    mock_client.register.return_value = {"ticket_id": str(new_ticket_id)}

    service = TicketService(client=mock_client, repo=mock_repo, idem_repo=mock_idem_repo)

    result = await service.create_ticket(
        event_id=event_id,
        first_name="Иван",
        last_name="Иванов",
        email="ivan@example.com",
        seat="A1",
        idempotency_key=str(key_id),
    )

    assert result == str(new_ticket_id)
    mock_idem_repo.delete_key.assert_awaited_once_with(str(key_id))
    mock_idem_repo.create_key.assert_awaited_once()
    mock_repo.create.assert_awaited_once()
