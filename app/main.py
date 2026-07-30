from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.factory import create_app

app = create_app(settings=get_settings())


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/db-health")
async def db_health(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(text("SELECT 1"))
    return {"db": "ok", "result": result.scalar_one()}
