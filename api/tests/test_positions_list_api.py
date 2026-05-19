import os
import sys
import unittest
from collections.abc import AsyncGenerator
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = API_DIR / "tests" / "test_positions_list.db"

sys.path.insert(0, str(API_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-positions-api-tests-only-32+chars"

from fastapi.testclient import TestClient  # noqa: E402

from core import user_context  # noqa: E402
from db import engine  # noqa: E402
from deps.auth import get_current_account_id  # noqa: E402
from main import app, seed_positions  # noqa: E402
from models.base import Base  # noqa: E402


async def _override_current_account_id() -> AsyncGenerator[str, None]:
    """单测绕过 JWT，固定绑定 user_id。"""
    reset = user_context.set_user_id("default_user")
    try:
        yield "default_user"
    finally:
        user_context.current_user_id.reset(reset)


class PositionsListApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        app.dependency_overrides[get_current_account_id] = _override_current_account_id
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_current_account_id, None)
        cls.client.close()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        seed_positions()

    def test_list_positions_returns_seeded_data(self) -> None:
        response = self.client.get("/api/v1/positions")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertGreaterEqual(len(payload["items"]), 5)
        first = payload["items"][0]
        self.assertIn("totalDividend", first)
        self.assertNotIn("annualDividend", first)

    def test_earnings_lens_returns_rows_and_summary(self) -> None:
        response = self.client.get("/api/v1/earnings-lens")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("mcWeighted", payload)
        self.assertIn("rows", payload)
        self.assertIn("totalMarketValue", payload["mcWeighted"])
        self.assertIn("positionCount", payload["summary"])
        self.assertIn("withBasicSnapshotCount", payload["summary"])
        self.assertGreaterEqual(payload["summary"]["positionCount"], 5)
        self.assertGreaterEqual(len(payload["rows"]), 5)
        first = payload["rows"][0]
        self.assertIn("code", first)
        self.assertIn("name", first)
        self.assertIn("snapshot", first)
        self.assertIn("annualReports", first)
        self.assertIsInstance(first["annualReports"], list)


if __name__ == "__main__":
    unittest.main()
