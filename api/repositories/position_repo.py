from sqlalchemy import select
from sqlalchemy.orm import Session

from models.position import Position


class PositionRepository:
    def list_positions(self, db: Session) -> list[Position]:
        stmt = select(Position).order_by(Position.code.asc())
        return list(db.scalars(stmt).all())

    def get_by_code(self, db: Session, code: str) -> Position | None:
        stmt = select(Position).where(Position.code == code)
        return db.scalar(stmt)

    def create_many(self, db: Session, positions: list[Position]) -> None:
        db.add_all(positions)

    def add_one(self, db: Session, position: Position) -> None:
        db.add(position)
