from __future__ import annotations

import httpx
import questionary
import typer

from dimensional_gateway.install import install as _install_service
from dimensional_gateway.install import is_installed, restart as _restart_service
from dimensional_gateway.install import uninstall as _uninstall_service

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
        _continue_session(existing_session_id, match["active_robot"])
    else:
        session_id, robot_name = _create_session(robot)
        _continue_session(session_id, robot_name)


def _create_session(robot: str | None) -> tuple[str, str]:
    robots = _get("/robots")
    if not robots:
        typer.echo("No robots found on the network.")
        raise typer.Exit(1)

    if robot is None:
        if len(robots) == 1:
            robot = robots[0]["name"]
        else:
            robot = questionary.select(
                "Select robot:",
                choices=[r["name"] for r in robots],
            ).ask()
            if robot is None:
                raise typer.Exit(0)

    resp = httpx.post(f"{_DAEMON_URL}/sessions", json={"robot": robot}, timeout=10.0)
    if resp.status_code == 404:
        typer.echo(f"Robot {robot!r} not found.")
        raise typer.Exit(1)
    resp.raise_for_status()
    return resp.json()["session_id"], robot


def _continue_session(session_id: str, robot: str) -> None:
    typer.echo(f"Connected to {robot}. Type 'exit' to quit.\n")
    _chat_loop(session_id)
    typer.echo(f"\nTo resume: dimctl chat --resume {session_id}")


def _chat_loop(session_id: str) -> None:
    while True:
        try:
            msg = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in ("exit", "quit"):
            break
        if not msg:
            continue
        with httpx.stream(
            "POST",
            f"{_DAEMON_URL}/sessions/{session_id}/chat",
            json={"message": msg},
            timeout=60.0,
        ) as r:
            if r.status_code == 503:
                typer.echo("Robot is no longer available. The session has been preserved.")
                break
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    typer.echo(line[6:])
        typer.echo()


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
    try:
        httpx.post(f"{_DAEMON_URL}/shutdown", timeout=3.0)
    except httpx.ConnectError:
        pass
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
