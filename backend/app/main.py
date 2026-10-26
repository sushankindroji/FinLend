import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, loans, notifications, users, voice, emi_calculator, explainability, enhanced_voice, blockchain
from app.core.config import get_settings
from app.core.security import decode_token
from app.db.mongodb import close_mongo_connection, connect_to_mongo, get_db
from app.services.realtime_service import get_realtime_service
from app.services.loan_service import detect_and_process_overdue_loans

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

_overdue_task: Optional[asyncio.Task] = None


async def _overdue_worker():
    """Background periodic task to detect and process overdue loans."""
    while True:
        try:
            await asyncio.sleep(60)
            db = get_db()
            await detect_and_process_overdue_loans(db)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.getLogger("finlend.worker").warning(f"Error in overdue loan worker: {e}")


@app.on_event("startup")
async def on_startup():
    global _overdue_task
    await connect_to_mongo()
    _overdue_task = asyncio.create_task(_overdue_worker())


@app.on_event("shutdown")
async def on_shutdown():
    global _overdue_task
    if _overdue_task:
        _overdue_task.cancel()
    await close_mongo_connection()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Real-time updates websocket endpoint."""
    await websocket.accept()
    realtime = get_realtime_service()
    user_id = None

    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                await realtime.connect_user(user_id, websocket)
        except Exception:
            pass

    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                event = data.get("event")
                payload_data = data.get("data", {})
                if event == "auth":
                    t = payload_data.get("token")
                    if t:
                        p = decode_token(t)
                        uid = p.get("sub")
                        if uid:
                            if user_id and user_id != uid:
                                await realtime.disconnect_user(user_id, websocket)
                            user_id = uid
                            await realtime.connect_user(user_id, websocket)

                elif event == "watch_loan":
                    lid = payload_data.get("loan_id")
                    if lid:
                        await realtime.watch_loan(lid, websocket)
                elif event == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "type": "pong", "data": {}}))
            except json.JSONDecodeError:
                pass
    except (WebSocketDisconnect, Exception):
        if user_id:
            await realtime.disconnect_user(user_id, websocket)


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
app.include_router(enhanced_voice.router)
app.include_router(emi_calculator.router)
app.include_router(explainability.router)
app.include_router(blockchain.router)
app.include_router(admin.router)
app.include_router(notifications.router)
