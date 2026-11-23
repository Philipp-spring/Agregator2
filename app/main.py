import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import settings
from app.database import async_engine
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
from app.routers import events, system, tickets
from app.workers import run_sync_outbox, run_sync_periodically

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

if settings.sentry_dsn:
    sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Приложение запущено")

    app.state.http_client = httpx.AsyncClient(
        base_url=settings.api_base_url,
        headers={"x-api-key": settings.api_key},
        timeout=httpx.Timeout(10.0, connect=5.0),
    )

    sync_task = asyncio.create_task(run_sync_periodically())
    outbox_task = asyncio.create_task(run_sync_outbox())
    logger.info("Фоновая синхронизация запущена!")
    yield

    sync_task.cancel()
    outbox_task.cancel()

    for task in (sync_task, outbox_task):
        try:
            await task
        except asyncio.CancelledError:
            pass

    await app.state.http_client.aclose()
    await async_engine.dispose()
    logger.info("Соединения с БД закрыты")


app = FastAPI(title="agregator", version="0.1.0", lifespan=lifespan)


@app.exception_handler(EventNotFoundError)
async def h_event_not_found(request: Request, exc: EventNotFoundError):
    """Событие не найдено в базе данных"""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(EventNotPublishedError)
async def h_event_not_published(request: Request, exc: EventNotPublishedError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RegistrationDeadlinePassedError)
async def h_deadline(request: Request, exc: RegistrationDeadlinePassedError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SeatNotAvailableError)
async def h_seat(request: Request, exc: SeatNotAvailableError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(TicketIdMissingError)
async def h_ticket_id(request: Request, exc: TicketIdMissingError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(ProviderError)
async def h_provider(request: Request, exc: ProviderError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(TicketNotFoundError)
async def h_ticket_not_found(request: Request, exc: TicketNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Ошибка валидации входных данных"},
    )

@app.exception_handler(IdempotencyConflictError)
async def idempotency_conflict_exception_handler(request: Request, exc: IdempotencyConflictError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


app.include_router(events.router)
app.include_router(tickets.router)
app.include_router(system.router)


@app.get("/")
async def welcome() -> dict:
    """Корневой маршрут"""
    return {"message": "Агрегатор"}



