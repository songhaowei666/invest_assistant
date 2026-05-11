import os
import sys
import unittest
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = API_DIR / "tests" / "test_invest_assistant.db"

sys.path.insert(0, str(API_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


class HealthApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
