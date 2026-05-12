"""Cron service for scheduling agent tasks.

存储层已从 workspace/cron/jobs.json + cron/action.jsonl 改为 PostgreSQL
（nanobot_cron_job 表，按 user_id 隔离）。

设计：
- self._store.jobs 在内存中保留"所有用户"的任务列表，timer 仍然按全局最近任务唤醒。
- self._job_user[job_id] 记录每个 job 所属的 user_id，_execute_job 时按此 set_user_id。
- 用户面向的公共方法（add/remove/update/enable/run/list/get）按 get_user_id() 过滤。
- 历史的 action.jsonl 跨进程合并机制在单进程 FastAPI 部署下不再需要，相关方法保留但不再被调用。
"""

import asyncio
import json
import os
import time
import uuid
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Literal

from filelock import FileLock
from loguru import logger

from nanobot_main.cron.types import (
    CronJob,
    CronJobState,
    CronPayload,
    CronRunRecord,
    CronSchedule,
    CronStore,
)

from core.user_context import get_user_id, use_user_id  # noqa: E402
from repositories.nanobot_cron_repo import NanobotCronRepo  # noqa: E402


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """Compute next run time in ms."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        # Next interval from now
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr:
        try:
            from zoneinfo import ZoneInfo

            from croniter import croniter
            # Use caller-provided reference time for deterministic scheduling
            base_time = now_ms / 1000
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(base_time, tz=tz)
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None

    return None


def _validate_schedule_for_add(schedule: CronSchedule) -> None:
    """Validate schedule fields that would otherwise create non-runnable jobs."""
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")

    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


class CronService:
    """Service for managing and executing scheduled jobs."""

    _MAX_RUN_HISTORY = 20

    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None,
        max_sleep_ms: int = 300_000,  # 5 minutes
    ):
        # store_path / action_path / 文件锁仅为签名兼容保留；PG 化后不再使用
        self.store_path = store_path
        self._action_path = store_path.parent / "action.jsonl"
        self._lock = FileLock(str(self._action_path.parent) + ".lock")
        self.on_job = on_job
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False
        self._timer_active = False
        self.max_sleep_ms = max_sleep_ms
        # PG 仓库 + 全局 job_id -> user_id 索引（timer 执行时用以回填 user 上下文）
        self._repo = NanobotCronRepo()
        self._job_user: dict[str, str] = {}

    def _load_jobs(self) -> tuple[list[CronJob], int] | None:
        """从 PG 加载所有用户的任务。

        Returns:
            ``(jobs, version)`` tuple；version 固定为 1（PG 化后不再使用版本号）。
            构建 CronJob 时通过 CronJob.from_dict 复用既有反序列化逻辑；同时回填
            ``self._job_user[job_id] = user_id`` 以供 _execute_job 使用。
        """
        try:
            grouped = self._repo.list_all_jobs_grouped()
        except Exception:
            logger.exception("Failed to load cron jobs from PG")
            return None

        jobs: list[CronJob] = []
        job_user: dict[str, str] = {}
        for user_id, job_dicts in grouped.items():
            for j in job_dicts:
                # _user_id 是 repo 注入的辅助字段，CronJob.from_dict 不识别 -> 弹出
                jd = dict(j)
                jd.pop("_user_id", None)
                try:
                    job = CronJob.from_dict(jd)
                except Exception:
                    logger.exception(
                        "Failed to deserialize cron job {} for user {}",
                        jd.get("id"),
                        user_id,
                    )
                    continue
                jobs.append(job)
                job_user[job.id] = user_id

        self._job_user = job_user
        return jobs, 1

    def _merge_action(self):
        """[deprecated] 旧版跨进程合并 action.jsonl 的逻辑；PG 化后单进程下不再需要，保留方法为空体。"""
        return

    def _load_store(self) -> CronStore | None:
        """Load jobs from disk. Reloads automatically if file was modified externally.
        - Reload every time because it needs to merge operations on the jobs object from other instances.
        - During _on_timer execution, return the existing store to prevent concurrent
          _load_store calls (e.g. from list_jobs polling) from replacing it mid-execution.
        - When the on-disk store exists but is unreadable: keep using the
          previous in-memory ``self._store`` if we already have one (so a
          transient corruption does not drop live jobs); only the very first
          load (during ``start``) can return ``None`` to signal an unrecoverable
          state to the caller.
        """
        if self._timer_active and self._store:
            return self._store
        loaded = self._load_jobs()
        if loaded is None:
            # Corrupt store on disk.  Prefer the last good in-memory snapshot
            # over wiping live jobs; ``_load_jobs`` has already moved the
            # corrupt file aside with a ``.corrupt-<ts>`` suffix.
            if self._store is not None:
                return self._store
            return None
        jobs, version = loaded
        self._store = CronStore(version=version, jobs=jobs)
        self._merge_action()

        return self._store

    def _save_store(self) -> None:
        """将当前内存中的 jobs 批量同步回 PG（按 user_id 分组覆盖写）。

        通过 self._job_user 将 jobs 分配到各 user_id；任何不在 _job_user 中的 job
        视为当前上下文用户的新增任务，user_id 取自 get_user_id()。
        """
        if not self._store:
            return

        try:
            current_uid = get_user_id()
        except Exception:
            current_uid = "default_user"

        grouped: dict[str, list[dict[str, Any]]] = {}
        for j in self._store.jobs:
            user_id = self._job_user.get(j.id) or current_uid
            self._job_user[j.id] = user_id
            grouped.setdefault(user_id, []).append(asdict(j))

        # 清理 _job_user 中已不存在的条目
        existing_ids = {j.id for j in self._store.jobs}
        for jid in list(self._job_user.keys()):
            if jid not in existing_ids:
                self._job_user.pop(jid, None)

        try:
            for user_id, jobs in grouped.items():
                self._repo.save_jobs(user_id, jobs)
        except Exception:
            logger.exception("Failed to save cron jobs to PG")
            raise

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """[deprecated] 原子写入文件的工具方法；PG 化后不再调用，保留实现以便参考。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            with suppress(PermissionError):
                fd = os.open(str(path.parent), os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        loaded = self._load_store()
        if loaded is None:
            # Store file existed but was corrupt and has been preserved with
            # a ``.corrupt-<ts>`` suffix.  Bail out instead of starting with
            # an empty store; that would call ``_save_store`` and overwrite
            # the now-renamed (but still recoverable) data with [].
            self._running = False
            raise RuntimeError(
                f"cron store at {self.store_path} is corrupt and was preserved; "
                "refusing to start with an empty job list. "
                "Inspect the .corrupt-<ts> backup and restore manually."
            )
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        logger.info("Cron service started with {} jobs", len(self._store.jobs if self._store else []))

    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs."""
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

    def _get_next_wake_ms(self) -> int | None:
        """Get the earliest next run time across all jobs."""
        if not self._store:
            return None
        times = [j.state.next_run_at_ms for j in self._store.jobs
                 if j.enabled and j.state.next_run_at_ms]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        """Schedule the next timer tick."""
        if self._timer_task:
            self._timer_task.cancel()

        if not self._running:
            return

        next_wake = self._get_next_wake_ms()
        if next_wake is None:
            delay_ms = self.max_sleep_ms
        else:
            delay_ms = min(self.max_sleep_ms, max(0, next_wake - _now_ms()))
        delay_s = delay_ms / 1000

        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())

    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        self._load_store()
        # If a hot reload found a corrupt store on disk, ``self._store`` may
        # still hold the previous, known-good in-memory snapshot.  Keep using
        # it rather than crashing the timer or wiping live jobs.
        if not self._store:
            self._arm_timer()
            return

        self._timer_active = True
        try:
            now = _now_ms()
            due_jobs = [
                j for j in self._store.jobs
                if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
            ]

            for job in due_jobs:
                await self._execute_job(job)

            self._save_store()
        finally:
            self._timer_active = False
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job.

        进入回调前按 self._job_user 解析 job 所属 user_id 并通过 use_user_id 注入上下文，
        让 on_job 内部的 SessionManager / MemoryStore 等 PG 仓库能命中正确用户。
        """
        start_ms = _now_ms()
        logger.info("Cron: executing job '{}' ({})", job.name, job.id)

        job_user_id = self._job_user.get(job.id) or "default_user"
        try:
            if self.on_job:
                with use_user_id(job_user_id):
                    await self.on_job(job)

            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info("Cron: job '{}' completed", job.name)

        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.exception("Cron: job '{}' failed", job.name)

        end_ms = _now_ms()
        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = end_ms

        job.state.run_history.append(CronRunRecord(
            run_at_ms=start_ms,
            status=job.state.last_status,
            duration_ms=end_ms - start_ms,
            error=job.state.last_error,
        ))
        job.state.run_history = job.state.run_history[-self._MAX_RUN_HISTORY:]

        # Handle one-shot jobs
        if job.schedule.kind == "at":
            if job.delete_after_run:
                self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            # Compute next run
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

    def _append_action(self, action: Literal["add", "del", "update"], params: dict):
        """[deprecated] 旧版跨进程动作队列；PG 化后改为直接同步 PG。

        为避免 action.jsonl 残留导致旧版进程读取错误，这里改为直接对 PG 执行等价操作。
        """
        try:
            current_uid = get_user_id()
        except Exception:
            current_uid = "default_user"
        try:
            if action == "del":
                job_id = params.get("job_id")
                if job_id:
                    self._repo.delete_job(current_uid, str(job_id))
                    self._job_user.pop(str(job_id), None)
                return
            # add / update：params 形如 asdict(CronJob)
            self._repo.upsert_job(current_uid, dict(params))
            jid = str(params.get("id", ""))
            if jid:
                self._job_user[jid] = current_uid
        except Exception:
            logger.exception("Failed to append action {} via PG", action)


    # ========== Public API ==========

    def _is_current_user_job(self, job: CronJob, current_uid: str) -> bool:
        """判断 job 是否属于当前用户。未在 _job_user 中（典型为本进程新创建尚未 _save_store
        的 job）时按当前 uid 处理；系统任务（system_event）不与用户隔离。"""
        owner = self._job_user.get(job.id)
        if owner is None:
            return True
        return owner == current_uid

    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List jobs for current user."""
        store = self._load_store()
        uid = get_user_id()
        scope = [j for j in store.jobs if self._is_current_user_job(j, uid)]
        jobs = scope if include_disabled else [j for j in scope if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
        channel_meta: dict | None = None,
        session_key: str | None = None,
    ) -> CronJob:
        """Add a new job."""
        _validate_schedule_for_add(schedule)
        now = _now_ms()

        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
                channel_meta=channel_meta or {},
                session_key=session_key,
            ),
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
        uid = get_user_id()
        self._job_user[job.id] = uid

        if self._running:
            store = self._load_store()
            store.jobs.append(job)
            self._save_store()
            self._arm_timer()
        else:
            self._append_action("add", asdict(job))

        logger.info("Cron: added job '{}' ({}) for user {}", name, job.id, uid)
        return job

    def register_system_job(self, job: CronJob) -> CronJob:
        """Register an internal system job (idempotent on restart).

        系统任务按当前 user_id 注册一份；不同用户的系统任务彼此独立。
        """
        store = self._load_store()
        now = _now_ms()
        job.state = CronJobState(next_run_at_ms=_compute_next_run(job.schedule, now))
        job.created_at_ms = now
        job.updated_at_ms = now
        store.jobs = [j for j in store.jobs if j.id != job.id]
        store.jobs.append(job)
        uid = get_user_id()
        self._job_user[job.id] = uid
        self._save_store()
        self._arm_timer()
        logger.info("Cron: registered system job '{}' ({}) for user {}", job.name, job.id, uid)
        return job

    def remove_job(self, job_id: str) -> Literal["removed", "protected", "not_found"]:
        """Remove a job by ID, unless it is a protected system job."""
        store = self._load_store()
        uid = get_user_id()
        job = next(
            (j for j in store.jobs if j.id == job_id and self._is_current_user_job(j, uid)),
            None,
        )
        if job is None:
            return "not_found"
        if job.payload.kind == "system_event":
            logger.info("Cron: refused to remove protected system job {}", job_id)
            return "protected"

        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before

        if removed:
            self._job_user.pop(job_id, None)
            if self._running:
                self._save_store()
                self._arm_timer()
            else:
                self._append_action("del", {"job_id": job_id})
            logger.info("Cron: removed job {} for user {}", job_id, uid)
            return "removed"

        return "not_found"

    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job."""
        store = self._load_store()
        uid = get_user_id()
        for job in store.jobs:
            if job.id == job_id and self._is_current_user_job(job, uid):
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                if self._running:
                    self._save_store()
                    self._arm_timer()
                else:
                    self._append_action("update", asdict(job))
                return job
        return None

    def update_job(
        self,
        job_id: str,
        *,
        name: str | None = None,
        schedule: CronSchedule | None = None,
        message: str | None = None,
        deliver: bool | None = None,
        channel: str | None = ...,
        to: str | None = ...,
        delete_after_run: bool | None = None,
    ) -> CronJob | Literal["not_found", "protected"]:
        """Update mutable fields of an existing job. System jobs cannot be updated.

        For ``channel`` and ``to``, pass an explicit value (including ``None``)
        to update; omit (sentinel ``...``) to leave unchanged.
        """
        store = self._load_store()
        uid = get_user_id()
        job = next(
            (j for j in store.jobs if j.id == job_id and self._is_current_user_job(j, uid)),
            None,
        )
        if job is None:
            return "not_found"
        if job.payload.kind == "system_event":
            return "protected"

        if schedule is not None:
            _validate_schedule_for_add(schedule)
            job.schedule = schedule
        if name is not None:
            job.name = name
        if message is not None:
            job.payload.message = message
        if deliver is not None:
            job.payload.deliver = deliver
        if channel is not ...:
            job.payload.channel = channel
        if to is not ...:
            job.payload.to = to
        if delete_after_run is not None:
            job.delete_after_run = delete_after_run

        job.updated_at_ms = _now_ms()
        if job.enabled:
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

        if self._running:
            self._save_store()
            self._arm_timer()
        else:
            self._append_action("update", asdict(job))

        logger.info("Cron: updated job '{}' ({})", job.name, job.id)
        return job

    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job without disturbing the service's running state."""
        was_running = self._running
        self._running = True
        uid = get_user_id()
        try:
            store = self._load_store()
            for job in store.jobs:
                if job.id == job_id and self._is_current_user_job(job, uid):
                    if not force and not job.enabled:
                        return False
                    await self._execute_job(job)
                    self._save_store()
                    return True
            return False
        finally:
            self._running = was_running
            if was_running:
                self._arm_timer()

    def get_job(self, job_id: str) -> CronJob | None:
        """Get a job by ID."""
        store = self._load_store()
        uid = get_user_id()
        return next(
            (j for j in store.jobs if j.id == job_id and self._is_current_user_job(j, uid)),
            None,
        )

    def status(self) -> dict:
        """Get service status."""
        store = self._load_store()
        uid = get_user_id()
        scope = [j for j in store.jobs if self._is_current_user_job(j, uid)]
        return {
            "enabled": self._running,
            "jobs": len(scope),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }
