"""从 api/tasks 目录扫描 @shared_task 注册名（AST，无需启动 Celery）。"""

from __future__ import annotations

import ast
from pathlib import Path

_TASKS_DIR = Path(__file__).resolve().parent
_SKIP_FILES = frozenset({"__init__.py", "discovery.py"})
# Beat 内部入口，不作为可配置的定时业务任务
_EXCLUDE_TASK_NAMES = frozenset({"tasks.scheduler.run_scheduled_task"})
_DECORATOR_NAMES = frozenset({"shared_task", "task"})


def _decorator_base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_celery_task_decorator(node: ast.expr) -> bool:
    return _decorator_base_name(node) in _DECORATOR_NAMES


def _task_name_from_decorator(
    node: ast.expr, module_name: str, func_name: str
) -> str | None:
    if not _is_celery_task_decorator(node):
        return None
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                value = kw.value.value
                if isinstance(value, str) and value:
                    return value
        if node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str) and value:
                return value
    return f"{module_name}.{func_name}"


def _extract_from_file(path: Path) -> list[str]:
    module_name = f"tasks.{path.stem}"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            task_name = _task_name_from_decorator(dec, module_name, node.name)
            if task_name:
                names.append(task_name)
                break
    return names


def list_task_keys_from_tasks_package() -> list[str]:
    """扫描 api/tasks/*.py 中带 @shared_task / @task 的函数，返回任务名列表。"""
    keys: list[str] = []
    for path in sorted(_TASKS_DIR.glob("*.py")):
        if path.name in _SKIP_FILES:
            continue
        keys.extend(_extract_from_file(path))
    return sorted(k for k in set(keys) if k not in _EXCLUDE_TASK_NAMES)
