from fastapi import APIRouter

from .bot import router as bot_router
from .earnings_lens import router as earnings_lens_router
from .positions import router as positions_router
from .scheduled_tasks import router as scheduled_tasks_router
from .sql_copilot import router as sql_copilot_router

api_router = APIRouter()
api_router.include_router(positions_router)
api_router.include_router(earnings_lens_router)
api_router.include_router(bot_router)
api_router.include_router(sql_copilot_router)
api_router.include_router(scheduled_tasks_router)
