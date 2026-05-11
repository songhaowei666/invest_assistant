import json
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph
from schemas.ai_modify import PositionChange


class AiState(TypedDict):
    instruction: str
    changes: list[PositionChange]
    reasoning: str
    risk_hints: list[str]


class PositionModifyGraph:
    """使用 LangGraph 编排指令解析流程，后续可替换真实 LLM 节点。"""

    def run(self, instruction: str) -> tuple[list[PositionChange], str, list[str]]:
        graph = StateGraph(AiState)
        graph.add_node("parse_instruction", self._parse_node)
        graph.set_entry_point("parse_instruction")
        graph.add_edge("parse_instruction", END)
        compiled = graph.compile()
        result = compiled.invoke(
            {
                "instruction": instruction,
                "changes": [],
                "reasoning": "",
                "risk_hints": [],
            }
        )
        return result["changes"], result["reasoning"], result["risk_hints"]

    def _parse_node(self, state: AiState) -> AiState:
        parsed_changes = self._parse_instruction(state["instruction"])
        reasoning = "已根据指令解析出结构化持仓修改建议。"
        risk_hints: list[str] = []
        if not parsed_changes:
            risk_hints.append("未识别到可执行修改，请检查指令是否包含股票代码与目标数值。")
        return {
            "instruction": state["instruction"],
            "changes": parsed_changes,
            "reasoning": reasoning,
            "risk_hints": risk_hints,
        }

    def _parse_instruction(self, instruction: str) -> list[PositionChange]:
        # 优先支持 JSON 指令，便于前端未来直接复用。
        stripped = instruction.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                records = parsed if isinstance(parsed, list) else [parsed]
                return [PositionChange(**record) for record in records]
            except Exception:
                return []

        # 自然语言格式示例：把 600519 仓位改成 100 股，成本改成 1500
        code_match = re.search(r"\b(\d{6})\b", instruction)
        if not code_match:
            return []

        shares_match = re.search(r"(仓位|持仓|股数).{0,6}?(\d+)", instruction)
        cost_match = re.search(r"(成本).{0,6}?(\d+(?:\.\d+)?)", instruction)
        dividend_match = re.search(r"(分红).{0,6}?(\d+(?:\.\d+)?)", instruction)

        change = PositionChange(code=code_match.group(1))
        if shares_match:
            change.positionShares = int(shares_match.group(2))
        if cost_match:
            change.positionCost = float(cost_match.group(2))
        if dividend_match:
            change.totalDividend = float(dividend_match.group(2))

        if (
            change.positionShares is None
            and change.positionCost is None
            and change.totalDividend is None
            and change.price is None
            and change.dividendYield is None
        ):
            return []
        return [change]
