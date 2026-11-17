"""DAHA backend: one FastAPI process. A's core routers + C's AI and discovery routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.ai.router import router as ai_router
from app.core.config import settings
from app.discovery.router import router as discovery_router
from app.routers import (
    auth,
    communities,
    conversations,
    health,
    items,
    notifications,
    requests,
    transactions,
    uploads,
    users,
)

app = FastAPI(title="DAHA API", version="0.1.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    health,
    auth,
    users,
    communities,
    uploads,
    items,
    requests,
    transactions,
    conversations,
    notifications,
):
    app.include_router(module.router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(discovery_router, prefix="/api")

settings.upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_path), name="uploads")
