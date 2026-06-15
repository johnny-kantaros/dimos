from __future__ import annotations

import json

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

_DAEMON_URL = "http://localhost:8128"


class _SessionGone(Exception):
    pass


async def _get_robots() -> list[dict]:  # type: ignore[type-arg]
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{_DAEMON_URL}/robots", timeout=5.0)
        r.raise_for_status()
        return r.json()


async def _create_session(robot: str) -> str:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{_DAEMON_URL}/sessions", json={"robot": robot}, timeout=60.0)
        if r.status_code == 404:
            raise ValueError(f"Robot {robot!r} not found")
        if r.status_code == 503:
            raise ConnectionError(f"Robot {robot!r} is not reachable")
        r.raise_for_status()
        return r.json()["session_id"]


async def _chat(session_id: str, message: str, on_status: object = None) -> str:
    """Stream a chat turn. Calls on_status(text) for each status event if provided."""
    async with httpx.AsyncClient() as c:
        async with c.stream(
            "POST",
            f"{_DAEMON_URL}/sessions/{session_id}/chat",
            json={"message": message},
            timeout=120.0,
        ) as r:
            if r.status_code == 404:
                raise _SessionGone()
            if r.status_code == 503:
                raise ConnectionError("robot unavailable")
            r.raise_for_status()
            tokens: list[str] = []
            async for line in r.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                if not isinstance(event, dict):
                    continue
                etype = event.get("type")
                if etype == "token":
                    tokens.append(event.get("content", ""))
                elif etype == "status" and callable(on_status):
                    await on_status(event.get("content", ""))
            return "".join(tokens)


class TelegramClient:
    def __init__(self, token: str, robot: str | None = None) -> None:
        self._default_robot = robot
        self._sessions: dict[int, tuple[str, str]] = {}  # chat_id -> (session_id, robot_name)
        self._app = Application.builder().token(token).build()
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("robots", self._on_robots))
        self._app.add_handler(CommandHandler("robot", self._on_robot))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

    async def start(self) -> None:
        await self._app.initialize()
        await self._app.updater.start_polling()
        await self._app.start()

    async def stop(self) -> None:
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    async def _resolve_session(self, chat_id: int) -> tuple[str, str] | None:
        if chat_id in self._sessions:
            return self._sessions[chat_id]
        return await self._new_session(chat_id)

    async def _new_session(self, chat_id: int, robot: str | None = None) -> tuple[str, str] | None:
        try:
            robots = await _get_robots()
        except (httpx.ConnectError, httpx.HTTPStatusError):
            return None
        if not robots:
            return None
        robot_name = robot or self._default_robot or robots[0]["name"]
        try:
            session_id = await _create_session(robot_name)
        except (ValueError, ConnectionError, httpx.HTTPStatusError, httpx.TimeoutException):
            return None
        self._sessions[chat_id] = (session_id, robot_name)
        return session_id, robot_name

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        result = await self._resolve_session(chat_id)
        if result is None:
            await update.message.reply_text("No robots found. Is dimwizard running?")
            return
        _, robot_name = result
        await update.message.reply_text(
            f"Connected to {robot_name}. Send a message to control the robot.\n\n"
            "/robot — show current robot\n"
            "/robot <name> — switch robot\n"
            "/robots — list all robots"
        )

    async def _on_robots(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            robots = await _get_robots()
        except httpx.ConnectError:
            await update.message.reply_text("Gateway daemon is not running.")
            return
        if not robots:
            await update.message.reply_text("No robots found on the network.")
            return
        await update.message.reply_text("\n".join(r["name"] for r in robots))

    async def _on_robot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args or []
        if not args:
            entry = self._sessions.get(chat_id)
            if entry:
                await update.message.reply_text(f"Current robot: {entry[1]}")
            else:
                await update.message.reply_text("No active session. Send a message to start one.")
            return
        robot_name = args[0]
        self._sessions.pop(chat_id, None)
        result = await self._new_session(chat_id, robot=robot_name)
        if result is None:
            await update.message.reply_text(f"Could not connect to robot {robot_name!r}.")
        else:
            await update.message.reply_text(f"Switched to {robot_name}.")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        text = (update.message.text or "").strip()
        if not text:
            return

        result = await self._resolve_session(chat_id)
        if result is None:
            await update.message.reply_text("No robots found. Is dimwizard running?")
            return

        session_id, robot_name = result
        status_msg = await update.message.reply_text("thinking...")

        async def _on_status(content: str) -> None:
            try:
                await status_msg.edit_text(content.strip() or "thinking...")
            except Exception:
                pass

        try:
            response = await _chat(session_id, text, on_status=_on_status)
        except _SessionGone:
            self._sessions.pop(chat_id, None)
            result = await self._new_session(chat_id)
            if result is None:
                await status_msg.edit_text("Session expired and no robot is available.")
                return
            session_id, _ = result
            try:
                response = await _chat(session_id, text)
            except Exception:
                await status_msg.edit_text("Failed to reconnect. Try again.")
                return
        except ConnectionError:
            await status_msg.edit_text(f"Robot {robot_name!r} is no longer reachable.")
            return
        except httpx.ConnectError:
            await status_msg.edit_text("Gateway daemon is not running.")
            return

        await status_msg.edit_text(response or "(no response)")
