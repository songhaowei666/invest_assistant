import os
import sys
import unittest
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = API_DIR / "tests" / "test_positions_list.db"

sys.path.insert(0, str(API_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from db import engine  # noqa: E402
from main import app, seed_positions  # noqa: E402
from models.base import Base  # noqa: E402


class PositionsListApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
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


if __name__ == "__main__":
    unittest.main()
