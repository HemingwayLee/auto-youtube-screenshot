from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.screenshots import ScreenshotError, is_youtube_url, random_screenshots


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: create tables for any models imported above. Switch to Alembic once the schema settles.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="auto-youtube-screenshot", lifespan=lifespan)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    version = db.execute(text("SELECT version()")).scalar_one()
    return {"status": "ok", "database": version}


class ScreenshotRequest(BaseModel):
    url: str
    count: int = Field(default=5, ge=1, le=20)


@app.post("/api/screenshots")
def screenshots(req: ScreenshotRequest):
    if not is_youtube_url(req.url):
        raise HTTPException(status_code=400, detail="Please enter a valid YouTube URL")
    try:
        return random_screenshots(req.url, req.count)
    except ScreenshotError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
