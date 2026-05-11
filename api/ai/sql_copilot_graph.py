from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[reportMissingImports]
from langchain_openai import ChatOpenAI  # type: ignore[reportMissingImports]
from langgraph.graph import END, StateGraph  # type: ignore[reportMissingImports]
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from configs.config import settings
from core.text2sql_vanna_stock import text2sql_query
from db import SessionLocal


class SqlCopilotState(TypedDict):
    session_id: str
    user_id: str
    question: str
    short_term_history: list[dict[str, Any]]
    long_term_memories: list[str]
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    answer: str
    error: str


class SqlCopilotGraph:
    """SQL Copilot 工作流：记忆读取 -> SQL 生成 -> 安全校验执行 -> 结果总结 -> 记忆写回。"""

    def __init__(self, memory_store: Any):
        self.memory_store = memory_store
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=0.2,
        )
        self._compiled = self._build_graph()

    def run(self, *, session_id: str, user_id: str, question: str) -> dict[str, Any]:
        state: SqlCopilotState = {
            "session_id": session_id,
            "user_id": user_id,
            "question": question,
            "short_term_history": [],
            "long_term_memories": [],
            "sql": "",
            "columns": [],
            "rows": [],
            "answer": "",
            "error": "",
        }
        result = self._compiled.invoke(state)
        return {
            "session_id": session_id,
            "question": question,
            "sql": result.get("sql", ""),
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "answer": result.get("answer", ""),
            "error": result.get("error", ""),
        }

    def _build_graph(self):
        graph = StateGraph(SqlCopilotState)
        graph.add_node("load_memory", self._load_memory_node)
        graph.add_node("build_sql_and_query", self._build_sql_and_query_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("save_memory", self._save_memory_node)
        graph.set_entry_point("load_memory")
        graph.add_edge("load_memory", "build_sql_and_query")
        graph.add_edge("build_sql_and_query", "summarize")
        graph.add_edge("summarize", "save_memory")
        graph.add_edge("save_memory", END)
        return graph.compile()

    def _load_memory_node(self, state: SqlCopilotState) -> SqlCopilotState:
        short_term = self.memory_store.get_recent_messages(
            session_id=state["session_id"], user_id=state["user_id"], limit=20
        )
        long_term = self.memory_store.search_related_memories(
            session_id=state["session_id"],
            user_id=state["user_id"],
            query=state["question"],
            limit=6,
        )
        state["short_term_history"] = short_term
        state["long_term_memories"] = long_term
        return state

    def _build_sql_and_query_node(self, state: SqlCopilotState) -> SqlCopilotState:
        # 临时仅保留短期记忆拼接：长期 mem0 召回暂不参与提示词。
        context_block = self._build_context_block(state["short_term_history"], [])
        enriched_question = f"{context_block}\n\n用户当前问题：{state['question']}"
        # query_result = text2sql_query(enriched_question)
        query_result = text2sql_query(enriched_question)
        sql = (query_result.get("sql") or "").strip()
        state["sql"] = sql

        if not self._is_safe_select_sql(sql):
            state["error"] = "生成的 SQL 未通过只读安全校验，仅允许 SELECT 查询。"
            state["columns"] = []
            state["rows"] = []
            return state

        try:
            rows, columns = self._run_select_sql(sql)
            state["rows"] = rows
            state["columns"] = columns
        except SQLAlchemyError as exc:
            # 仅保留必要错误语义，避免把底层异常细节直接传给用户。
            error_hint = str(exc).splitlines()[0]
            state["error"] = f"SQL 执行失败：{error_hint}"
            state["rows"] = []
            state["columns"] = []
        return state

    def _summarize_node(self, state: SqlCopilotState) -> SqlCopilotState:
        if state["error"]:
            polished_error = self._polish_error_message(
                question=state["question"],
                sql=state["sql"],
                raw_error=state["error"],
            )
            state["answer"] = polished_error
            state["error"] = polished_error
            return state

        rows_preview = state["rows"][:50]
        messages = [
            SystemMessage(
                content=(
                    "你是股票 SQL Copilot。请基于 SQL 查询结果输出中文总结："
                    "1) 先给结论；2) 给关键数据点；3) 给口径提醒；"
                    "4) 不编造结果中不存在的数据。"
                )
            ),
            HumanMessage(
                content=(
                    f"用户问题：{state['question']}\n"
                    f"SQL：{state['sql']}\n"
                    f"列名：{state['columns']}\n"
                    f"结果（最多 50 行）：{json.dumps(rows_preview, ensure_ascii=False)}"
                )
            ),
        ]
        summary = self.llm.invoke(messages).content
        state["answer"] = str(summary or "").strip()
        return state

    def _save_memory_node(self, state: SqlCopilotState) -> SqlCopilotState:
        payload = {
            "question": state["question"],
            "sql": state["sql"],
            "columns": state["columns"],
            "rows_preview": state["rows"][:10],
            "answer": state["answer"],
            "error": state["error"],
        }
        self.memory_store.add_turn_memory(
            session_id=state["session_id"],
            user_id=state["user_id"],
            content=json.dumps(payload, ensure_ascii=False),
        )
        return state

    def _build_context_block(
        self, short_term_history: list[dict[str, Any]], long_term_memories: list[str]
    ) -> str:
        lines: list[str] = [
            "你可以参考以下历史上下文，但必须以本次查询实际结果为准。",
            "【短期记忆（最近20条）】",
        ]
        for item in short_term_history[:20]:
            role = str(item.get("role", "unknown"))
            content = str(item.get("content", "")).strip()
            if content:
                lines.append(f"- {role}: {content}")
        lines.append("【长期记忆（mem0召回）】")
        for memory in long_term_memories:
            mem = str(memory).strip()
            if mem:
                lines.append(f"- {mem}")
        return "\n".join(lines)

    def _is_safe_select_sql(self, sql: str) -> bool:
        if not sql:
            return False
        normalized = sql.strip().lower()
        if not (normalized.startswith("select") or normalized.startswith("with")):
            return False
        # 拦截危险语句，避免误执行写操作
        dangerous = re.compile(
            r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge)\b",
            re.IGNORECASE,
        )
        return dangerous.search(sql) is None

    def _run_select_sql(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        with SessionLocal() as db:
            assert isinstance(db, Session)
            result = db.execute(text(sql))
            columns = list(result.keys())
            data_rows = result.fetchmany(size=200)
            rows = [dict(zip(columns, row, strict=False)) for row in data_rows]
            return rows, columns

    def _polish_error_message(self, *, question: str, sql: str, raw_error: str) -> str:
        # 将底层异常润色成用户可理解的反馈，避免直接暴露数据库报错细节。
        messages = [
            SystemMessage(
                content=(
                    "你是股票 SQL Copilot 的错误解释助手。"
                    "请将技术错误改写为中文用户提示，要求："
                    "1) 不暴露数据库驱动、堆栈、库名等实现细节；"
                    "2) 先说明本次查询未成功；"
                    "3) 简要说明可能原因；"
                    "4) 给出下一步可执行建议（如改问法或指定字段/时间口径）；"
                    "5) 语气简洁专业，不要编造数据。"
                )
            ),
            HumanMessage(
                content=(
                    f"用户问题：{question}\n"
                    f"生成SQL：{sql}\n"
                    f"原始错误：{raw_error}"
                )
            ),
        ]
        polished = self.llm.invoke(messages).content
        return str(polished or "").strip()
