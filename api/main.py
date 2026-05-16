from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from configs.config import settings
from controllers.router import api_router
from db import SessionLocal, engine
from extensions import init_extensions
from core.scheduled_celery import get_celery_app_or_none, sync_beat_schedule
from models.base import Base
from models.position import Position
from repositories.position_repo import PositionRepository


app = FastAPI(title=settings.APP_NAME)
# Celery 等在 extensions.init_extensions 内初始化（含 app.state.celery）
init_extensions(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.API_PREFIX)


def seed_positions() -> None:
    repo = PositionRepository()
    seed_data = [
        {"code": "600519", "name": "贵州茅台", "price": 1728.36, "market_value": 207403.2, "position_shares": 120, "position_cost": 1680.5, "dividend_yield": 0.032, "annual_dividend": 62.3},
        {"code": "601328", "name": "交通银行", "price": 7.12, "market_value": 21360.0, "position_shares": 3000, "position_cost": 6.18, "dividend_yield": 0.057, "annual_dividend": 0.38},
        {"code": "600900", "name": "长江电力", "price": 25.08, "market_value": 37620.0, "position_shares": 1500, "position_cost": 23.65, "dividend_yield": 0.039, "annual_dividend": 0.94},
        {"code": "601088", "name": "中国神华", "price": 40.52, "market_value": 36468.0, "position_shares": 900, "position_cost": 30.12, "dividend_yield": 0.071, "annual_dividend": 2.28},
        {"code": "600036", "name": "招商银行", "price": 36.74, "market_value": 29392.0, "position_shares": 800, "position_cost": 33.47, "dividend_yield": 0.049, "annual_dividend": 1.74},
    ]
    with SessionLocal() as db:
        if repo.list_positions(db):
            return
        models = [Position(**item) for item in seed_data]
        repo.create_many(db, models)
        db.commit()


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    seed_positions()
    if get_celery_app_or_none() is not None:
        with SessionLocal() as db:
            sync_beat_schedule(db)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
