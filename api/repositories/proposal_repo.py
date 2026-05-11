from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.proposal import AiModifyProposal


class ProposalRepository:
    def create(self, db: Session, proposal: AiModifyProposal) -> None:
        db.add(proposal)

    def get_by_id(self, db: Session, proposal_id: str) -> AiModifyProposal | None:
        stmt = select(AiModifyProposal).where(AiModifyProposal.id == proposal_id)
        return db.scalar(stmt)

    def get_by_request_id(self, db: Session, request_id: str) -> AiModifyProposal | None:
        stmt = select(AiModifyProposal).where(AiModifyProposal.request_id == request_id)
        return db.scalar(stmt)

    def mark_applied(self, proposal: AiModifyProposal, request_id: str) -> None:
        proposal.status = "applied"
        proposal.request_id = request_id
        proposal.applied_at = datetime.utcnow()
