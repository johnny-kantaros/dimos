from __future__ import annotations

import os
import signal
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dimensional_gateway.discovery import Discovery
from dimensional_gateway.registry import RobotRegistry
from dimensional_gateway.session import ChatSession, SessionStore

_registry = RobotRegistry()
_sessions = SessionStore()
_discovery: Discovery | None = None



class SessionCreate(BaseModel):
    robot: str

class SessionInfo(BaseModel):
    session_id: str
    active_robot: str

class ChatRequest(BaseModel):
    message: str



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # type: ignore[type-arg]
    global _discovery
    _discovery = Discovery(on_add=_registry.add, on_remove=_registry.remove)
    yield
    if _discovery:
        _discovery.close()


app = FastAPI(title="Dimensional Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/robots")
def list_robots() -> list[dict[str, Any]]:
    return [{"name": r.name, "lcm_url": r.lcm_url, "address": r.address} for r in _registry.list()]


@app.post("/sessions", response_model=SessionInfo)
def create_session(body: SessionCreate) -> SessionInfo:
    if _registry.get(body.robot) is None:
        raise HTTPException(404, f"Robot {body.robot!r} not found")
    session = _sessions.create(active_robot=body.robot)
    return SessionInfo(session_id=session.session_id, active_robot=session.active_robot)


@app.get("/sessions", response_model=list[SessionInfo])
def list_sessions() -> list[SessionInfo]:
    return [SessionInfo(session_id=s.session_id, active_robot=s.active_robot) for s in _sessions.list_all()]


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    if _sessions.get(session_id) is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    _sessions.delete(session_id)
    return {"status": "deleted"}


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest) -> StreamingResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    if _registry.get(session.active_robot) is None:
        raise HTTPException(503, f"Robot {session.active_robot!r} is no longer available")
    await session.append("user", body.message)
    return StreamingResponse(_stub_response(session, body.message), media_type="text/event-stream")


async def _stub_response(session: ChatSession, message: str) -> AsyncIterator[str]:
    reply = f"[stub] {session.active_robot} received: {message!r}"
    yield f"data: {reply}\n\n"
    yield "data: [DONE]\n\n"
    await session.append("assistant", reply)


@app.post("/shutdown")
def shutdown() -> dict[str, str]:
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "stopping"}
