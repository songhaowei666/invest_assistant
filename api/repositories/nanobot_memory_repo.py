"""nanobot 记忆存储仓库：封装 SOUL/USER/MEMORY.md/history/cursor 的 PG 访问。

行龄计算：基于 nanobot_memory_md 表的 updated_at 字段；写入时仅对内容变化的行
刷新时间戳，保留未变更行的旧时间（替代原 GitStore 的 line_ages 能力）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import asc, delete, desc, func, select

from db import SessionLocal
from models.nanobot_memory_cursor import NanobotMemoryCursor
from models.nanobot_memory_file import NanobotMemoryFile
from models.nanobot_memory_history import NanobotMemoryHistory
from models.nanobot_memory_md import NanobotMemoryMd


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _split_lines(text: str) -> list[str]:
    """按行切分（不丢空行、不强制保留 \\n）。

    与原 file.read_text + str.splitlines() 行为一致。"""
    return text.splitlines()


class NanobotMemoryRepo:
    """SOUL/USER/MEMORY/history/cursor 的统一仓库。"""

    # ---- SOUL.md / USER.md ----

    def read_file(self, user_id: str, name: str) -> str:
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotMemoryFile)
                .where(NanobotMemoryFile.user_id == user_id)
                .where(NanobotMemoryFile.name == name)
            )
            return row.content if row else ""

    def write_file(self, user_id: str, name: str, content: str) -> None:
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotMemoryFile)
                .where(NanobotMemoryFile.user_id == user_id)
                .where(NanobotMemoryFile.name == name)
            )
            now = _utcnow()
            if row is None:
                db.add(
                    NanobotMemoryFile(
                        user_id=user_id,
                        name=name,
                        content=content,
                        updated_at=now,
                    )
                )
            else:
                row.content = content
                row.updated_at = now
            db.commit()

    # ---- MEMORY.md（按行 + 行龄） ----

    def read_memory_md(self, user_id: str) -> str:
        """按 line_no 升序读出后用 \\n 拼接（不在末尾追加换行）。"""
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotMemoryMd)
                    .where(NanobotMemoryMd.user_id == user_id)
                    .order_by(asc(NanobotMemoryMd.line_no))
                )
            )
            return "\n".join(r.content or "" for r in rows)

    def write_memory_md(self, user_id: str, content: str) -> None:
        """按行 diff 写入：内容相同的行保留 updated_at，差异行刷新；多余旧行删除。"""
        new_lines = _split_lines(content or "")
        now = _utcnow()
        with SessionLocal() as db:
            existing = list(
                db.scalars(
                    select(NanobotMemoryMd)
                    .where(NanobotMemoryMd.user_id == user_id)
                    .order_by(asc(NanobotMemoryMd.line_no))
                )
            )
            existing_map = {r.line_no: r for r in existing}

            for idx, line in enumerate(new_lines):
                line_no = idx + 1
                row = existing_map.get(line_no)
                if row is None:
                    db.add(
                        NanobotMemoryMd(
                            user_id=user_id,
                            line_no=line_no,
                            content=line,
                            updated_at=now,
                        )
                    )
                else:
                    if (row.content or "") != line:
                        row.content = line
                        row.updated_at = now

            max_keep = len(new_lines)
            for row in existing:
                if row.line_no > max_keep:
                    db.delete(row)

            db.commit()

    def line_ages_for_memory_md(self, user_id: str) -> list[float]:
        """返回按 line_no 升序的"距今天数"列表（含小数）。"""
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotMemoryMd)
                    .where(NanobotMemoryMd.user_id == user_id)
                    .order_by(asc(NanobotMemoryMd.line_no))
                )
            )
            now = _utcnow()
            ages: list[float] = []
            for r in rows:
                ts = r.updated_at
                if ts is None:
                    ages.append(0.0)
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                delta = now - ts
                ages.append(max(0.0, delta.total_seconds() / 86400.0))
            return ages

    # ---- history ----

    def get_cursor_value(self, user_id: str, name: str) -> int:
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotMemoryCursor)
                .where(NanobotMemoryCursor.user_id == user_id)
                .where(NanobotMemoryCursor.name == name)
            )
            return int(row.value) if row else 0

    def set_cursor_value(self, user_id: str, name: str, value: int) -> None:
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotMemoryCursor)
                .where(NanobotMemoryCursor.user_id == user_id)
                .where(NanobotMemoryCursor.name == name)
            )
            if row is None:
                db.add(
                    NanobotMemoryCursor(
                        user_id=user_id,
                        name=name,
                        value=int(value),
                    )
                )
            else:
                row.value = int(value)
            db.commit()

    def append_history(
        self,
        *,
        user_id: str,
        timestamp: str,
        content: str,
    ) -> int:
        """追加一条 history 记录并将 cursor 自增；返回新 cursor 值。"""
        with SessionLocal() as db:
            cursor_row = db.scalar(
                select(NanobotMemoryCursor)
                .where(NanobotMemoryCursor.user_id == user_id)
                .where(NanobotMemoryCursor.name == "cursor")
            )
            if cursor_row is None:
                # 兜底：如果 cursor 表为空但 history 有残留数据，使用 history 的最大 cursor + 1
                fallback = int(
                    db.scalar(
                        select(func.coalesce(func.max(NanobotMemoryHistory.cursor), 0))
                        .where(NanobotMemoryHistory.user_id == user_id)
                    )
                    or 0
                )
                next_cursor = fallback + 1
                db.add(
                    NanobotMemoryCursor(
                        user_id=user_id,
                        name="cursor",
                        value=next_cursor,
                    )
                )
            else:
                next_cursor = int(cursor_row.value or 0) + 1
                cursor_row.value = next_cursor

            db.add(
                NanobotMemoryHistory(
                    user_id=user_id,
                    cursor=next_cursor,
                    timestamp=timestamp,
                    content=content,
                )
            )
            db.commit()
            return next_cursor

    def read_unprocessed_history(
        self, user_id: str, since_cursor: int
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotMemoryHistory)
                    .where(NanobotMemoryHistory.user_id == user_id)
                    .where(NanobotMemoryHistory.cursor > since_cursor)
                    .order_by(asc(NanobotMemoryHistory.cursor))
                )
            )
            return [
                {
                    "cursor": int(r.cursor),
                    "timestamp": r.timestamp,
                    "content": r.content or "",
                }
                for r in rows
            ]

    def count_history(self, user_id: str) -> int:
        with SessionLocal() as db:
            return int(
                db.scalar(
                    select(func.count(NanobotMemoryHistory.id))
                    .where(NanobotMemoryHistory.user_id == user_id)
                )
                or 0
            )

    def compact_history(self, user_id: str, keep_last_n: int) -> int:
        """仅保留最新 keep_last_n 条，返回删除条数。"""
        if keep_last_n <= 0:
            return 0
        with SessionLocal() as db:
            total = int(
                db.scalar(
                    select(func.count(NanobotMemoryHistory.id))
                    .where(NanobotMemoryHistory.user_id == user_id)
                )
                or 0
            )
            if total <= keep_last_n:
                return 0
            # 取出第 keep_last_n 大的 cursor 作为保留下界
            threshold_row = db.scalar(
                select(NanobotMemoryHistory.cursor)
                .where(NanobotMemoryHistory.user_id == user_id)
                .order_by(desc(NanobotMemoryHistory.cursor))
                .offset(keep_last_n - 1)
                .limit(1)
            )
            if threshold_row is None:
                return 0
            result = db.execute(
                delete(NanobotMemoryHistory)
                .where(NanobotMemoryHistory.user_id == user_id)
                .where(NanobotMemoryHistory.cursor < threshold_row)
            )
            db.commit()
            return int(result.rowcount or 0)
