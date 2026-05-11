import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parent
TEST_DB_PATH = API_DIR / "tests" / "test_sql_copilot_api.db"
OUTPUT_DIR = API_DIR / "tests" / "outputs"

sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from controllers.sql_copilot import router as sql_copilot_router  # noqa: E402


class SqlCopilotApiTestCase(unittest.TestCase):
    api_outputs: list[dict[str, object]] = []

    @classmethod
    def setUpClass(cls) -> None:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        app = FastAPI()
        app.include_router(sql_copilot_router, prefix="/api/v1")
        cls.client = TestClient(app)
        cls.api_outputs = []

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        cls._write_outputs_markdown()

    @classmethod
    def _record_output(cls, *, endpoint: str, method: str, params: dict, response: dict) -> None:
        cls.api_outputs.append(
            {
                "endpoint": endpoint,
                "method": method,
                "params": params,
                "response": response,
            }
        )

    @classmethod
    def _write_outputs_markdown(cls) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{Path(__file__).stem}_{ts}.md"
        output_path = OUTPUT_DIR / file_name

        lines: list[str] = [
            "# SQL Copilot 接口测试输出",
            "",
            f"- 脚本: `{Path(__file__).name}`",
            f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`",
            "",
        ]
        for idx, item in enumerate(cls.api_outputs, start=1):
            lines.extend(
                [
                    f"## {idx}. {item['method']} {item['endpoint']}",
                    "",
                    "### 请求参数",
                    "```json",
                    json.dumps(item["params"], ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "### 接口返回",
                    "```json",
                    json.dumps(item["response"], ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"outputs markdown: {output_path}")

    @patch("controllers.sql_copilot.SqlCopilotService")
    def test_query_scope_api(self, mock_service_cls) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.query_scope.return_value = {
            "tables": {
                "stock_basic_info": [{"name": "code", "type": "VARCHAR(20)", "nullable": False, "comment": "股票编码"}],
                "stock_financial_report": [
                    {"name": "report_period", "type": "VARCHAR(16)", "nullable": False, "comment": "报告期"}
                ],
            },
            "scope_summary": "这是可查询范围摘要。",
            "meta": {"embedding_model": "text-embedding-3-large", "embedding_dimensions": 3072},
        }

        response = self.client.get("/api/v1/sql-copilot/query-scope")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print("query-scope response:", json.dumps(payload, ensure_ascii=False))
        self._record_output(
            endpoint="/api/v1/sql-copilot/query-scope",
            method="GET",
            params={},
            response=payload,
        )
        self.assertIn("tables", payload)
        self.assertIn("scope_summary", payload)

    @patch("controllers.sql_copilot.SqlCopilotService")
    def test_chat_api(self, mock_service_cls) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.chat.return_value = {
            "session_id": "demo-session-001",
            "question": "查询 600519 最近五个年报的 ROE",
            "sql": "SELECT report_period, roe FROM stock_financial_report LIMIT 5;",
            "columns": ["report_period", "roe"],
            "rows": [{"report_period": "20241231", "roe": 31.2}],
            "answer": "这是总结内容。",
            "error": "",
        }

        req = {
            "session_id": "demo-session-001",
            "user_id": "song",
            "question": "查询 600519 最近五个年报的 ROE",
        }
        response = self.client.post("/api/v1/sql-copilot/chat", json=req)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print("chat response:", json.dumps(payload, ensure_ascii=False))
        self._record_output(
            endpoint="/api/v1/sql-copilot/chat",
            method="POST",
            params=req,
            response=payload,
        )
        self.assertEqual(payload.get("session_id"), "demo-session-001")
        self.assertIn("sql", payload)

    @patch("controllers.sql_copilot.SqlCopilotService")
    def test_chat_api_without_session_id(self, mock_service_cls) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.chat.return_value = {
            "session_id": "sqlc-auto-001",
            "question": "查询 601328 最新市盈率",
            "sql": "SELECT pe FROM stock_basic_info WHERE code = '601328';",
            "columns": ["pe"],
            "rows": [{"pe": 5.6}],
            "answer": "已返回交通银行最新市盈率。",
            "error": "",
        }

        req = {
            "user_id": "song",
            "question": "查询 601328 最新市盈率",
        }
        response = self.client.post("/api/v1/sql-copilot/chat", json=req)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print("chat(no session_id) response:", json.dumps(payload, ensure_ascii=False))
        self._record_output(
            endpoint="/api/v1/sql-copilot/chat",
            method="POST",
            params=req,
            response=payload,
        )
        self.assertIn("session_id", payload)

    @patch("controllers.sql_copilot.SqlCopilotService")
    def test_sessions_list_api(self, mock_service_cls) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.list_sessions.return_value = {
            "sessions": [
                {
                    "session_id": "demo-session-001",
                    "user_id": "song",
                    "title": "查询茅台 ROE",
                    "preview": "查询 600519 最近五个年报的 ROE",
                    "created_at": "2026-05-09T16:00:00+08:00",
                    "updated_at": "2026-05-09T16:05:00+08:00",
                    "message_count": 4,
                }
            ]
        }

        req = {"user_id": "song", "limit": 50}
        response = self.client.post("/api/v1/sql-copilot/sessions/list", json=req)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print("sessions/list response:", json.dumps(payload, ensure_ascii=False))
        self._record_output(
            endpoint="/api/v1/sql-copilot/sessions/list",
            method="POST",
            params=req,
            response=payload,
        )
        self.assertIn("sessions", payload)

    @patch("controllers.sql_copilot.SqlCopilotService")
    def test_sessions_delete_api(self, mock_service_cls) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.delete_session.return_value = {"deleted": True}

        req = {"session_id": "demo-session-001", "user_id": "song"}
        response = self.client.post("/api/v1/sql-copilot/sessions/delete", json=req)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        print("sessions/delete response:", json.dumps(payload, ensure_ascii=False))
        self._record_output(
            endpoint="/api/v1/sql-copilot/sessions/delete",
            method="POST",
            params=req,
            response=payload,
        )
        self.assertEqual(payload.get("deleted"), True)


if __name__ == "__main__":
    unittest.main()
