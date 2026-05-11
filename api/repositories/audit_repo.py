from sqlalchemy.orm import Session

from models.audit import AuditLog


class AuditRepository:
    def create(self, db: Session, audit_log: AuditLog) -> None:
        db.add(audit_log)
