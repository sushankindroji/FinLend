import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, loans, notifications, users, voice
from app.core.config import get_settings
from app.db.mongodb import close_mongo_connection, connect_to_mongo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title="FinLend - Voice-Enabled P2P Micro-Lending Platform",
    description=(
        "Academic prototype. All financial transactions are SIMULATED. "
        "This is not a real financial institution and does not process real money."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await connect_to_mongo()


@app.on_event("shutdown")
async def on_shutdown():
    await close_mongo_connection()


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "2.0.0",
        "disclaimer": "Simulated academic prototype only.",
    }


# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(loans.router)
app.include_router(voice.router)
app.include_router(admin.router)
app.include_router(notifications.router)
