from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AiModifyProposal(Base):
    __tablename__ = "ai_modify_proposals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instruction: Mapped[str] = mapped_column(Text)
    changes_json: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    risk_hints_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
