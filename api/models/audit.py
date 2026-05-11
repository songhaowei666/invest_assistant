from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100))
    proposal_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    operator: Mapped[str] = mapped_column(String(100), default="system")
    instruction: Mapped[str] = mapped_column(Text)
    model_summary: Mapped[str] = mapped_column(Text)
    before_snapshot_json: Mapped[str] = mapped_column(Text)
    after_snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
