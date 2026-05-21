import asyncio
import os
import sys
import warnings
from pathlib import Path

# 加载含 DreamConfig 的 pydantic 模型时会触发 protected namespace 提示，脚本里可忽略
warnings.filterwarnings(
    "ignore",
    message=".*conflict with protected namespace.*",
    category=UserWarning,
)

# 本文件在 api/core/：需把仓库根加入 path 才能 import api.*；把 api/ 加入 path 才能 import nanobot_main
_core_dir = Path(__file__).resolve().parent
_api_dir = _core_dir.parent
_repo_root = _api_dir.parent
for _p in (_repo_root, _api_dir):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# 与 api 同级下的 .nanobot（配置、工作区）
WORKSPACE = _api_dir / ".nanobot"

from configs.config import settings
from nanobot_main.agent.hook import AgentHook, AgentHookContext
from nanobot_main.agent.loop import AgentLoop
from nanobot_main.agent.skills import SkillsLoader
from nanobot_main.bus.queue import MessageBus
from nanobot_main.config.loader import load_config
from nanobot_main.nanobot import Nanobot
from nanobot_main.providers.factory import make_provider


def build_bot() -> Nanobot:
    openai_api_key = settings.DASHSCOPE_API_KEY
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not openai_api_key:
        print("[Error] OPENAI_API_KEY not set")
        sys.exit(1)

    # db_path = WORKSPACE / "data" / "stock_history.db"
    # if not db_path.exists():
    #     print(f"[Error] stock db not found: {db_path}")
    #     sys.exit(1)

    config = load_config(WORKSPACE /  "config.json")
    config.providers.custom.api_key = settings.OPENAI_API_KEY
    config.providers.custom.api_base = settings.OPENAI_BASE_URL
    config.agents.defaults.workspace = str(WORKSPACE)
# config.agents.defaults.model = "qwen3.5-plus"
    config.agents.defaults.model = "gpt-3.5-turbo"
    config.agents.defaults.provider = "custom"

    # workspace 技能目录：替代 .nanobot/skills，builtin 仍用 nanobot_main/skills
    workspace_skills_dir = _api_dir / "skills"
    # mcp_servers = dict(config.tools.mcp_servers or {})
    # tavily_mcp = mcp_servers.get("tavily-mcp")
    # if tavily_mcp is not None:
    #     tavily_mcp.env = dict(tavily_mcp.env or {})
    #     tavily_mcp.env["TAVILY_API_KEY"] = tavily_key

    provider = make_provider(config)
    defaults = config.agents.defaults
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=WORKSPACE,
        model=defaults.model,
        max_iterations=defaults.max_tool_iterations,
        context_window_tokens=defaults.context_window_tokens,
        max_tool_result_chars=defaults.max_tool_result_chars,
        web_config=config.tools.web,
        exec_config=config.tools.exec,
        restrict_to_workspace=False,
        # mcp_servers=mcp_servers,
        timezone=defaults.timezone,
        disabled_skills=defaults.disabled_skills or None,
    )
    loop.context.skills = SkillsLoader(
        WORKSPACE,
        workspace_skills_dir=workspace_skills_dir,
        disabled_skills=set(defaults.disabled_skills) if defaults.disabled_skills else None,
    )

    image_dir = WORKSPACE / "image_show"
    # loop.tools.register(QueryStockSQLTool(db_path, image_dir))
    # loop.tools.register(ArimaStockTool(db_path, image_dir))
    # loop.tools.register(BollDetectionTool(db_path, image_dir))
    return Nanobot(loop)


 


if __name__ == "__main__":
    # 仅控制台脚本：不打印 nanobot_main 的 DEBUG，避免刷屏；iteration 0 之后往往在等 API，长时间无新日志属正常
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    # 进度与结果用 flush=True，避免管道/重定向时缓冲导致「长时间看不到任何输出」
    print("正在初始化 Agent...", flush=True)
    bot = build_bot()
    print("正在调用模型（首包可能需数十秒至数分钟，请稍候）...", flush=True)
    result = asyncio.run(
        bot.run("你有哪些技能")
    )
    print("----- 模型回复 -----", flush=True)
    print(result.content or "(空回复)", flush=True)
    if result.tools_used:
        print("使用的工具:", ", ".join(result.tools_used), flush=True)



























    