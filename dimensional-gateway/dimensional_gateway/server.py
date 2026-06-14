from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dimensional_gateway.agent import run_agent
from dimensional_gateway.discovery import Discovery
from dimensional_gateway.robot_registry import RobotRegistry
from dimensional_gateway.session import SessionStore

_registry = RobotRegistry()
_sessions = SessionStore()
_discovery: Discovery | None = None


class RobotResponse(BaseModel):
    name: str
    lcm_url: str
    address: str


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
    await asyncio.to_thread(_registry.stop_all_connections)


app = FastAPI(title="Dimensional Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/robots", response_model=list[RobotResponse])
def list_robots() -> list[RobotResponse]:
    return [RobotResponse(name=r.name, lcm_url=r.lcm_url, address=r.address) for r in _registry.list()]


@app.post("/sessions", response_model=SessionInfo)
async def create_session(body: SessionCreate) -> SessionInfo:
    robot = _registry.get(body.robot)
    if robot is None:
        raise HTTPException(404, f"Robot {body.robot!r} not found")
    try:
        await asyncio.to_thread(_registry.get_connection, body.robot)
    except RuntimeError:
        raise HTTPException(503, f"Robot {body.robot!r} is not reachable")
    session = _sessions.create(robot=robot)
    await asyncio.to_thread(session.skills._build_cache)
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


async def _agent_stream(session: object, request: Request) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for chunk in run_agent(session):  # type: ignore[arg-type]
                await queue.put(chunk)
        finally:
            await queue.put(None)

    task = asyncio.create_task(produce())

    async def cancel_on_disconnect() -> None:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                return
            await asyncio.sleep(0.3)

    watcher = asyncio.create_task(cancel_on_disconnect())

    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            yield chunk
    finally:
        watcher.cancel()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(task, watcher, return_exceptions=True)


@app.post("/sessions/{session_id}/chat")
async def chat(session_id: str, body: ChatRequest, request: Request) -> StreamingResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"Session {session_id!r} not found")
    if _registry.get(session.active_robot) is None:
        raise HTTPException(503, f"Robot {session.active_robot!r} is no longer available")
    await session.append("user", body.message)
    return StreamingResponse(_agent_stream(session, request), media_type="text/event-stream")


@app.post("/shutdown")
async def shutdown(background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(os.kill, os.getpid(), signal.SIGTERM)
    return {"status": "stopping"}
