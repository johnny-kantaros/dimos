from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dimensional_harness.connection import ConnectionPool
from dimensional_harness.discovery import Discovery
from dimensional_harness.registry import RobotRegistry
from dimensional_harness.session import SessionStore

_registry = RobotRegistry()
_sessions = SessionStore()
_pool = ConnectionPool()
_discovery: Discovery | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    global _discovery
    _discovery = Discovery(on_add=_registry.add, on_remove=_registry.remove)
    yield
    _pool.close_all()
    if _discovery:
        _discovery.close()


app = FastAPI(title="Dimensional Harness", version="0.1.0", lifespan=lifespan)


# ── Models ────────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    robot: str


class SessionInfo(BaseModel):
    session_id: str
    active_robot: str


# ── Robots ────────────────────────────────────────────────────────────────────

@app.get("/robots")
def list_robots() -> list[dict[str, Any]]:
    return [
        {
            "name": r.name,
            "lcm_url": r.lcm_url,
            "robot_type": r.robot_type,
            "version": r.version,
            "status": r.status,
            "blueprint": r.blueprint,
            "address": r.address,
            "gateway_url": r.gateway_url,
        }
        for r in _registry.list()
    ]


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionInfo)
def create_session(body: SessionCreate) -> SessionInfo:
    if _registry.get(body.robot) is None:
        raise HTTPException(404, f"Robot {body.robot!r} not found on the network")
    session = _sessions.create(active_robot=body.robot)
    return SessionInfo(session_id=session.session_id, active_robot=session.active_robot)


@app.get("/sessions")
def list_sessions() -> list[SessionInfo]:
    return [
        SessionInfo(session_id=s.session_id, active_robot=s.active_robot)
        for s in _sessions.list_all()
    ]


class SessionUpdate(BaseModel):
    active_robot: str


@app.patch("/sessions/{session_id}", response_model=SessionInfo)
def update_session(session_id: str, body: SessionUpdate) -> SessionInfo:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    if _registry.get(body.active_robot) is None:
        raise HTTPException(404, f"Robot {body.active_robot!r} not found on the network")
    session.active_robot = body.active_robot
    return SessionInfo(session_id=session.session_id, active_robot=session.active_robot)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    if _sessions.get(session_id) is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    _sessions.delete(session_id)
    return {"status": "deleted"}


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest) -> StreamingResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id!r} not found")

    robot = _registry.get(session.active_robot)
    conn = _pool.get(robot.name, robot.lcm_url) if robot else None

    session.append("user", body.message)
    return StreamingResponse(_run_agent(session, conn), media_type="text/event-stream")


async def _run_agent(session: Any, conn: Any) -> AsyncIterator[str]:
    # TODO: replace with real ReAct loop (Day 3)
    last_user_msg = session.get_history()[-1].content
    placeholder = f"[harness stub] robot={session.active_robot!r} heard: {last_user_msg!r}"
    session.append("assistant", placeholder)

    yield f"data: {placeholder}\n\n"
    yield "data: [DONE]\n\n"
