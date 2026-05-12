"""nanobot 定时任务存储仓库：替代 cron/jobs.json 与 cron/action.jsonl。

按 (user_id, job_id) 作为主键约束；CronJob ↔ JSONB 字段以 dataclass.asdict / 反序列化
完成转换，避免硬编码字段。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, select

from db import SessionLocal
from models.nanobot_cron_job import NanobotCronJob


def _cron_job_to_dict(job: Any) -> dict[str, Any]:
    """CronJob -> JSONB 拆分前的纯 dict 形态。"""
    return asdict(job)


def _row_to_dict(row: NanobotCronJob) -> dict[str, Any]:
    """PG row -> 与 nanobot CronJob.from_dict 兼容的 dict。"""
    return {
        "id": row.job_id,
        "name": row.name,
        "enabled": bool(row.enabled),
        "schedule": dict(row.schedule_json or {}),
        "payload": dict(row.payload_json or {}),
        "state": dict(row.state_json or {}),
        "created_at_ms": int(row.created_at_ms or 0),
        "updated_at_ms": int(row.updated_at_ms or 0),
        "delete_after_run": bool(row.delete_after_run),
        # 行级冗余的 user_id 用于 cron timer 执行时回填上下文
        "_user_id": row.user_id,
    }


class NanobotCronRepo:
    """定时任务表的访问入口。"""

    def list_jobs(self, user_id: str) -> list[dict[str, Any]]:
        """返回某用户下所有任务（含 disabled），结构兼容 CronJob.from_dict。"""
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotCronJob)
                    .where(NanobotCronJob.user_id == user_id)
                    .order_by(NanobotCronJob.id.asc())
                )
            )
            return [_row_to_dict(r) for r in rows]

    def list_all_jobs_grouped(self) -> dict[str, list[dict[str, Any]]]:
        """返回所有用户的任务，按 user_id 分组；CronService 启动时整体加载用。"""
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotCronJob).order_by(
                        NanobotCronJob.user_id.asc(), NanobotCronJob.id.asc()
                    )
                )
            )
            grouped: dict[str, list[dict[str, Any]]] = {}
            for r in rows:
                grouped.setdefault(r.user_id, []).append(_row_to_dict(r))
            return grouped

    def upsert_job(self, user_id: str, job_dict: dict[str, Any]) -> None:
        """按 (user_id, job_id) upsert。job_dict 由 CronJob asdict 得到。"""
        job_id = str(job_dict.get("id", ""))
        if not job_id:
            raise ValueError("job_dict missing 'id'")
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotCronJob)
                .where(NanobotCronJob.user_id == user_id)
                .where(NanobotCronJob.job_id == job_id)
            )
            schedule = dict(job_dict.get("schedule") or {})
            payload = dict(job_dict.get("payload") or {})
            state = dict(job_dict.get("state") or {})
            if row is None:
                row = NanobotCronJob(
                    user_id=user_id,
                    job_id=job_id,
                    name=str(job_dict.get("name", "")),
                    enabled=bool(job_dict.get("enabled", True)),
                    schedule_json=schedule,
                    payload_json=payload,
                    state_json=state,
                    created_at_ms=int(job_dict.get("created_at_ms", 0) or 0),
                    updated_at_ms=int(job_dict.get("updated_at_ms", 0) or 0),
                    delete_after_run=bool(job_dict.get("delete_after_run", False)),
                )
                db.add(row)
            else:
                row.name = str(job_dict.get("name", row.name))
                row.enabled = bool(job_dict.get("enabled", row.enabled))
                row.schedule_json = schedule
                row.payload_json = payload
                row.state_json = state
                row.created_at_ms = int(job_dict.get("created_at_ms", row.created_at_ms) or 0)
                row.updated_at_ms = int(job_dict.get("updated_at_ms", row.updated_at_ms) or 0)
                row.delete_after_run = bool(job_dict.get("delete_after_run", row.delete_after_run))
            db.commit()

    def save_jobs(self, user_id: str, jobs: list[dict[str, Any]]) -> None:
        """整体覆盖某用户的任务：以传入列表为准，删除多余的、upsert 列表中的。"""
        with SessionLocal() as db:
            current_rows = list(
                db.scalars(
                    select(NanobotCronJob).where(NanobotCronJob.user_id == user_id)
                )
            )
            keep_ids = {str(j.get("id", "")) for j in jobs if j.get("id")}
            for row in current_rows:
                if row.job_id not in keep_ids:
                    db.delete(row)
            db.flush()

            existing = {r.job_id: r for r in current_rows if r.job_id in keep_ids}
            for j in jobs:
                job_id = str(j.get("id", ""))
                if not job_id:
                    continue
                schedule = dict(j.get("schedule") or {})
                payload = dict(j.get("payload") or {})
                state = dict(j.get("state") or {})
                if job_id in existing:
                    row = existing[job_id]
                    row.name = str(j.get("name", row.name))
                    row.enabled = bool(j.get("enabled", row.enabled))
                    row.schedule_json = schedule
                    row.payload_json = payload
                    row.state_json = state
                    row.created_at_ms = int(j.get("created_at_ms", row.created_at_ms) or 0)
                    row.updated_at_ms = int(j.get("updated_at_ms", row.updated_at_ms) or 0)
                    row.delete_after_run = bool(j.get("delete_after_run", row.delete_after_run))
                else:
                    db.add(
                        NanobotCronJob(
                            user_id=user_id,
                            job_id=job_id,
                            name=str(j.get("name", "")),
                            enabled=bool(j.get("enabled", True)),
                            schedule_json=schedule,
                            payload_json=payload,
                            state_json=state,
                            created_at_ms=int(j.get("created_at_ms", 0) or 0),
                            updated_at_ms=int(j.get("updated_at_ms", 0) or 0),
                            delete_after_run=bool(j.get("delete_after_run", False)),
                        )
                    )
            db.commit()

    def delete_job(self, user_id: str, job_id: str) -> bool:
        with SessionLocal() as db:
            result = db.execute(
                delete(NanobotCronJob)
                .where(NanobotCronJob.user_id == user_id)
                .where(NanobotCronJob.job_id == job_id)
            )
            db.commit()
            return bool(result.rowcount or 0)
