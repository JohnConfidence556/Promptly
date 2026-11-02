import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.builds import router as builds_router
from app.api.projects import router as projects_router
from app.config import ALLOWED_ORIGINS
from app.db.database import init_db
from app.services import tracing

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    tracing.flush


app = FastAPI(title="Promptly API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(builds_router)
app.include_router(projects_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}