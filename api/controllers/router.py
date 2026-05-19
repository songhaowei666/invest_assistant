from fastapi import APIRouter, Depends

from deps.auth import get_current_account_id

from .auth import router as auth_router
from .bot import router as bot_router
from .earnings_lens import router as earnings_lens_router
from .positions import router as positions_router
from .scheduled_tasks import router as scheduled_tasks_router
from .sql_copilot import router as sql_copilot_router

api_router = APIRouter()
api_router.include_router(auth_router)
# 持仓接口需登录：未带合法 Bearer access 的请求统一 401（并绑定 user_context）
api_router.include_router(positions_router, dependencies=[Depends(get_current_account_id)])
api_router.include_router(earnings_lens_router)
api_router.include_router(bot_router)
api_router.include_router(sql_copilot_router)
api_router.include_router(scheduled_tasks_router)
