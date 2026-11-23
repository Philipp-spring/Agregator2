import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime

import httpx

from app.clients.provider import EventsProviderClient
from app.config import settings
from app.enums import EventStatus
from app.exceptions import (
    EventNotFoundError,
    EventNotPublishedError,
    IdempotencyConflictError,
    ProviderError,
    RegistrationDeadlinePassedError,
    SeatNotAvailableError,
    TicketIdMissingError,
    TicketNotFoundError,
)
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.tickets import SQLAlchemyTicketRepository

logger = logging.getLogger(__name__)


class TicketService:
    """Бизнес-сценарий создания билета с интеграцией провайдера."""
    def __init__(self, 
                 client: EventsProviderClient, 
                 repo: SQLAlchemyTicketRepository, 
                 idem_repo: IdempotencyRepository):
        self.client = client
        self.repo = repo
        self.idem_repo = idem_repo
    

    def _calculate_hash(self, event_id, first_name, last_name, email, seat) -> str:
        """Вычисление хэша запроса"""
        canonical = {
            "event_id": str(event_id),
            "first_name": first_name.strip().lower(),
            "last_name": last_name.strip().lower(),
            "email": email.strip().lower(),
            "seat": seat.strip().lower(),
        }
        raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    
    async def create_ticket(
        self, event_id: uuid.UUID, first_name: str, last_name: str, email: str, seat: str, idempotency_key: str | None = None
    ) -> str:
        """логика билета"""

        req_hash = None
        if idempotency_key:
            req_hash = self._calculate_hash(event_id, first_name, last_name, email, seat)
            existing = await self.idem_repo.get_key(idempotency_key)
            if existing:
                if (datetime.now(UTC) - existing.created_at).total_seconds() >= settings.idempotency_ttl_seconds:
                    await self.idem_repo.delete_key(idempotency_key)
                else:
                    if existing.request_hash != req_hash:
                        raise IdempotencyConflictError("ключ идемпотентности уже использован с другими данными")
                    return str(existing.ticket_id)


        event = await self.repo.get_event(event_id)
        if not event:
            logger.warning("Попытка регистрации на несуществующее событие %s", event_id)
            raise EventNotFoundError("Событие не найдено")

        if event.status != EventStatus.PUBLISHED.value:
            raise EventNotPublishedError("Регистрация доступна только для опубликованных событий")

        now = datetime.now(UTC)
        deadline = event.registration_deadline.astimezone(UTC)
        if now >= deadline:
            raise RegistrationDeadlinePassedError("Срок регистрации на это мероприятие истек")
        try:
            seats_data = await self.client.get_seats(event_id)
        except httpx.HTTPError as e:
            raise ProviderError(f"Не удалось проверить места: {e}")

        if seat not in seats_data.get("seats", []):
            raise SeatNotAvailableError(f"Место {seat} занято или не существует")

        try:
            response_data = await self.client.register(
                event_id=event_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                seat=seat,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"Ошибка регистрации: {e}")

        ticket_id = response_data.get("ticket_id")
        if not ticket_id:
            raise TicketIdMissingError("Внешний API не вернул ticket_id")

        await self.repo.create(
            event_id=event_id,
            ticket_id=uuid.UUID(ticket_id),
            first_name=first_name,
            last_name=last_name,
            email=email,
            seat=seat,
        )

        if idempotency_key:
            await self.idem_repo.create_key(
                key=idempotency_key, 
                request_hash=req_hash, 
                ticket_id=uuid.UUID(ticket_id)
            )

        await self.repo.commit()

        logger.info("Успешная регистрация билета %s у провайдера и в локальной БД", ticket_id)
        return ticket_id

    async def cancel_ticket(self, ticket_id: uuid.UUID) -> None:
        """Отмена регистрации (билета): удаление у провайдера и в БД."""
        ticket = await self.repo.get_ticket_by_id(ticket_id)
        if not ticket:
            logger.warning("Попытка отмены несуществующего билета %s", ticket_id)
            raise TicketNotFoundError("Билет не найден")
        try:
            await self.client.unregister(ticket.event_id, ticket_id)
        except httpx.HTTPError as e:
            raise ProviderError(f"Не удалось отменить билет у провайдера: {e}")

        await self.repo.delete(ticket_id)
        await self.repo.commit()

        logger.info("Билет %s успешно отменён", ticket_id)
