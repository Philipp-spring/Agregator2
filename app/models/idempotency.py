import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdempotencyKey(Base):
    __tablename__="idempotency_keys"

    key: Mapped[str] = mapped_column(String(250), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), 
            ForeignKey("tickets.id", ondelete="CASCADE"), 
            nullable=False
            )
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), 
            server_default=func.now(), 
            nullable=False)




