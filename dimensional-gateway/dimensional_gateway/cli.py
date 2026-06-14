from __future__ import annotations

import json
import threading
import time

import httpx
from prompt_toolkit import prompt as _pt_prompt
from prompt_toolkit.key_binding import KeyBindings
import questionary
import typer

from dimensional_gateway.install import (
    install as _install_service,
    is_installed,
    restart as _restart_service,
    uninstall as _uninstall_service,
)

app = typer.Typer(help="dimctl — Dimensional robot control plane")

_DAEMON_URL = "http://localhost:8128"


@app.command(name="list-robots")
def list_robots() -> None:
    """List robots discovered on the network."""
    robots = _get("/robots")
    if not robots:
        typer.echo("No robots found. Is dimwizard running on a robot?")
        return
    for r in robots:
        typer.echo(f"  {r['name']}  lcm={r.get('lcm_url', '')}  addr={r.get('address', '')}")


@app.command(name="list-sessions")
def list_sessions() -> None:
    """List active chat sessions."""
    sessions = _get("/sessions")
    if not sessions:
        typer.echo("No active sessions.")
        return
    for s in sessions:
        typer.echo(f"  {s['session_id']}  robot={s['active_robot']}")


@app.command()
def chat(
    robot: str | None = typer.Option(None, "--robot", "-r"),
    existing_session_id: str | None = typer.Option(None, "--resume"),
) -> None:
    """Chat with a robot. Use --resume <session_id> to rejoin an existing session."""
    if existing_session_id is not None:
        sessions = _get("/sessions")
        match = next((s for s in sessions if s["session_id"] == existing_session_id), None)
        if match is None:
            typer.echo(f"Session {existing_session_id!r} not found.")
            raise typer.Exit(1)
        _print_history(existing_session_id)
        _continue_session(existing_session_id, match["active_robot"])
    else:
        session_id, robot_name = _create_session(robot)
        _continue_session(session_id, robot_name)


def _create_session(robot: str | None) -> tuple[str, str]:
    if robot is None:
        robot = _select_robot()

    resp = httpx.post(f"{_DAEMON_URL}/sessions", json={"robot": robot}, timeout=60.0)
    if resp.status_code == 404:
        typer.echo(f"Robot {robot!r} not found.")
        raise typer.Exit(1)
    if resp.status_code == 503:
        typer.echo(f"Robot {robot!r} is not reachable. Is dimwizard running on the robot?")
        raise typer.Exit(1)
    resp.raise_for_status()
    data = resp.json()
    warnings = data.get("warnings", [])
    for w in warnings:
        typer.echo(f"Warning: {w}", err=True)
    if warnings:
        typer.echo(err=True)
    return data["session_id"], data["active_robot"]


def _select_robot() -> str:
    robots = _get("/robots")
    if not robots:
        typer.echo("No robots found on the network.")
        raise typer.Exit(1)
    if len(robots) == 1:
        return robots[0]["name"]
    robot = questionary.select("Select robot:", choices=[r["name"] for r in robots]).ask()
    if robot is None:
        raise typer.Exit(0)
    return robot


def _print_history(session_id: str) -> None:
    try:
        resp = httpx.get(f"{_DAEMON_URL}/sessions/{session_id}/history", timeout=5.0)
        resp.raise_for_status()
        messages = resp.json()
    except httpx.HTTPError:
        return
    for msg in messages:
        if msg["role"] == "user":
            typer.echo(f"\n> {msg['content']}")
        elif msg["role"] == "assistant":
            typer.echo(f"\n{msg['content']}")


def _continue_session(session_id: str, robot: str) -> None:
    typer.echo(f"Connected to {robot}. Type 'exit' to detach.\n")
    _chat_loop(session_id)
    typer.echo(f"\nTo resume:\n  dimctl chat --resume {session_id}")


def _spinner(stop: threading.Event) -> None:
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop.is_set():
        typer.echo(f"\r{frames[i % len(frames)]} thinking...", nl=False)
        time.sleep(0.08)
        i += 1
    typer.echo("\r" + " " * 14 + "\r", nl=False)


def _start_spinner() -> tuple[threading.Event, threading.Thread]:
    stop = threading.Event()
    t = threading.Thread(target=_spinner, args=(stop,), daemon=True)
    t.start()
    return stop, t


def _stop_spinner(stop: threading.Event, t: threading.Thread, timeout: float | None = None) -> None:
    if not stop.is_set():
        stop.set()
        t.join(timeout=timeout)


def _stream_response(session_id: str, msg: str) -> bool:
    """Stream a chat response. Returns True if interrupted by Ctrl+C."""
    with httpx.stream(
        "POST",
        f"{_DAEMON_URL}/sessions/{session_id}/chat",
        json={"message": msg},
        timeout=1000,
    ) as r:
        if r.status_code == 503:
            typer.echo("Robot is no longer available. The session has been preserved.")
            return False
        r.raise_for_status()
        stop, t = _start_spinner()
        first_token = True
        try:
            for line in r.iter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                etype = event.get("type") if isinstance(event, dict) else "token"

                if etype == "token":
                    _stop_spinner(stop, t)
                    if first_token:
                        typer.echo()
                        first_token = False
                    typer.echo(event["content"], nl=False)
                    time.sleep(0.06)
                elif etype == "status":
                    _stop_spinner(stop, t)
                    for ch in event["content"]:
                        typer.echo(ch, nl=False)
                        time.sleep(0.02)
                    typer.echo()
                    stop, t = _start_spinner()
                elif etype == "thinking":
                    if stop.is_set():
                        stop, t = _start_spinner()
        except KeyboardInterrupt:
            _stop_spinner(stop, t, timeout=0.2)
            typer.echo()
            return True
        finally:
            stop.set()
            t.join(timeout=0.2)
    typer.echo()
    return False


def _read_input() -> str | None:
    """Prompt for input. Returns None when Ctrl+C is pressed on an empty line (exit signal).
    Ctrl+C with text on the line clears the text and keeps the prompt open."""
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event):
        if event.current_buffer.text:
            event.current_buffer.reset()
        else:
            raise KeyboardInterrupt()

    try:
        return _pt_prompt("> ", key_bindings=kb)
    except (KeyboardInterrupt, EOFError):
        return None


def _chat_loop(session_id: str) -> None:
    ctrl_c_count = 0

    while True:
        typer.echo()
        msg = _read_input()

        if msg is None:
            ctrl_c_count += 1
            if ctrl_c_count >= 2:
                break
            typer.echo("(Ctrl+C again to exit, or type 'exit')")
            continue

        msg = msg.strip()
        if msg.lower() in ("exit", "quit"):
            break
        if not msg:
            continue

        ctrl_c_count = 0
        if _stream_response(session_id, msg):
            ctrl_c_count += 1
            typer.echo("[Interrupted]")


@app.command()
def status() -> None:
    """Show daemon status and discovered robots."""
    installed = is_installed()
    typer.echo(f"service:  {'installed' if installed else 'not installed'}")
    try:
        robots = httpx.get(f"{_DAEMON_URL}/robots", timeout=3.0).json()
        typer.echo("daemon:   running")
        if robots:
            for r in robots:
                typer.echo(f"  {r['name']}  lcm={r.get('lcm_url', '')}  addr={r.get('address', '')}")
        else:
            typer.echo("  no robots discovered")
    except httpx.ConnectError:
        typer.echo("daemon:   not running")


@app.command()
def install() -> None:
    """Install dimctl as a login service (starts on boot, restarts on crash)."""
    _install_service()


@app.command()
def uninstall() -> None:
    """Stop the daemon and remove the login service."""
    _uninstall_service()


@app.command()
def restart() -> None:
    """Restart the dimctl daemon."""
    _restart_service()


def _get(path: str) -> list:  # type: ignore[type-arg]
    try:
        resp = httpx.get(f"{_DAEMON_URL}{path}", timeout=5.0)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except httpx.ConnectError:
        typer.echo("Gateway daemon is not running. Run 'dimctl install' to set it up.")
        raise typer.Exit(1)


def main() -> None:
    app()
