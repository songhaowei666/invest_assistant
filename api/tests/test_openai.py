# 本地直连 OpenAI 官方 API 的冒烟脚本（非 pytest 用例）：python api/tests/test_openai.py

import sys
from pathlib import Path

_tests_dir = Path(__file__).resolve().parent
_api_dir = _tests_dir.parent
_repo_root = _api_dir.parent
for _p in (_repo_root, _api_dir):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from api.configs.config import settings  # noqa: E402

import openai  # noqa: E402


def main() -> None:
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello, world!"}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
