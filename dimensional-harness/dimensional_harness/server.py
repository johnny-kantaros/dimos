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
    robot_name: str


class SessionInfo(BaseModel):
    session_id: str
    robot_name: str


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
        }
        for r in _registry.list()
    ]


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionInfo)
def create_session(body: SessionCreate) -> SessionInfo:
    robot = _registry.get(body.robot_name)
    if robot is None:
        raise HTTPException(404, f"Robot {body.robot_name!r} not found on the network")
    session = _sessions.create(robot_name=body.robot_name)
    # Eagerly open the connection so the caller knows immediately if the robot
    # is unreachable rather than failing on the first chat turn.
    conn = _pool.get(robot.name, robot.lcm_url)
    try:
        conn.acquire()
    except RuntimeError as exc:
        _sessions.delete(session.session_id)
        raise HTTPException(503, str(exc)) from exc
    return SessionInfo(session_id=session.session_id, robot_name=session.robot_name)


@app.get("/sessions")
def list_sessions() -> list[SessionInfo]:
    return [
        SessionInfo(session_id=s.session_id, robot_name=s.robot_name)
        for s in _sessions.list_all()
    ]


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

    robot = _registry.get(session.robot_name)
    if robot is None:
        raise HTTPException(503, f"Robot {session.robot_name!r} is no longer on the network")

    conn = _pool.get(robot.name, robot.lcm_url)
    session.append("user", body.message)

    return StreamingResponse(_run_agent(session, conn), media_type="text/event-stream")


async def _run_agent(session: Any, conn: Any) -> AsyncIterator[str]:
    # TODO: replace with real ReAct loop
    # For now: echo back with robot context so the wiring can be tested end-to-end
    robot_name = session.robot_name
    last_user_msg = session.get_history()[-1].content

    placeholder = f"[harness stub] robot={robot_name!r} heard: {last_user_msg!r}"
    session.append("assistant", placeholder)

    yield f"data: {placeholder}\n\n"
    yield "data: [DONE]\n\n"
