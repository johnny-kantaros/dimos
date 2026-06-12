from __future__ import annotations

import httpx
import typer

app = typer.Typer(help="dimctl — Dimensional robot command center")

DAEMON_URL = "http://localhost:8128"


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8128, "--port", help="Port"),
) -> None:
    """Start the harness daemon."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("uvicorn not installed. Run: pip install uvicorn[standard]")
        raise typer.Exit(1)
    uvicorn.run("dimensional_harness.server:app", host=host, port=port, reload=False)


@app.command(name="list-robots")
def list_robots() -> None:
    """List robots discovered on the network."""
    robots = _get("/robots")
    if not robots:
        typer.echo("No robots found. Is dimensional-gateway running on a robot?")
        return
    for r in robots:
        typer.echo(f"  {r['name']}  type={r['robot_type']}  lcm={r['lcm_url']}")


@app.command(name="list-sessions")
def list_sessions() -> None:
    """List active sessions."""
    sessions = _get("/sessions")
    if not sessions:
        typer.echo("No active sessions.")
        return
    for s in sessions:
        typer.echo(f"  {s['session_id']}  robot={s['active_robot']}")


@app.command()
def chat(
    robot: str | None = typer.Option(None, "--robot", "-r", help="Robot to connect to"),
) -> None:
    """Chat with a robot."""
    robots = _get("/robots")

    if not robots:
        typer.echo("No robots found on the network. Is dimensional-gateway running?")
        raise typer.Exit(1)

    _print_robot_summary(robots)

    if robot is None:
        robot = _select_robot(robots)
        if robot is None:
            raise typer.Exit(0)

    resp = httpx.post(f"{DAEMON_URL}/sessions", json={"robot": robot}, timeout=10.0)
    if resp.status_code == 404:
        typer.echo(resp.json().get("detail", "Robot not found."))
        raise typer.Exit(1)
    resp.raise_for_status()

    data = resp.json()
    session_id = data["session_id"]
    typer.echo(f"Active robot: {data['active_robot']}")
    typer.echo("Type a message, /help for commands, or 'exit' to quit.\n")

    try:
        while True:
            try:
                msg = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if msg.lower() in ("exit", "quit", "q"):
                break
            if not msg:
                continue

            if msg.startswith("/"):
                new_robot = _handle_slash(msg, robot, session_id)
                if new_robot:
                    robot = new_robot
                continue

            with httpx.stream(
                "POST",
                f"{DAEMON_URL}/sessions/{session_id}/chat",
                json={"message": msg},
                timeout=60.0,
            ) as stream_resp:
                stream_resp.raise_for_status()
                for line in stream_resp.iter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        typer.echo(line[6:])
            typer.echo()
    finally:
        httpx.delete(f"{DAEMON_URL}/sessions/{session_id}", timeout=5.0)


def _handle_slash(msg: str, robot: str, session_id: str) -> str | None:
    """Handle a slash command. Returns new active robot name if /switch was used."""
    cmd = msg.lstrip("/").lower().strip()

    if cmd in ("help", "?"):
        typer.echo( "  /robots             — list all robots on the network")
        typer.echo( "  /switch [robot]     — change active robot")
        typer.echo( "  /help               — show this message")
        return None

    if cmd == "robots":
        _print_robot_summary(_get("/robots"))
        return None

    if cmd.startswith("switch"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            robots = _get("/robots")
            _print_robot_summary(robots)
            new = _select_robot(robots)
        else:
            new = parts[1].strip()
        if not new or new == robot:
            return None
        resp = httpx.patch(f"{DAEMON_URL}/sessions/{session_id}", json={"active_robot": new}, timeout=5.0)
        if resp.status_code == 404:
            typer.echo(resp.json().get("detail", f"Robot {new!r} not found."))
            return None
        resp.raise_for_status()
        typer.echo(f"Switched to {new}")
        return new

    typer.echo(f"Unknown command: /{cmd}  (type /help for available commands)")
    return None


@app.command()
def install() -> None:
    """Install dimctl as a login service (starts on boot, restarts on crash)."""
    from dimensional_harness.install import install as _install
    _install()


@app.command()
def uninstall() -> None:
    """Remove the dimctl login service."""
    from dimensional_harness.install import uninstall as _uninstall
    _uninstall()


@app.command()
def restart() -> None:
    """Restart the dimctl daemon (picks up code changes)."""
    from dimensional_harness.install import restart as _restart
    _restart()


def _select_robot(robots: list) -> str | None:  # type: ignore[type-arg]
    if len(robots) == 1:
        return robots[0]["name"]
    import questionary
    names = [r["name"] for r in robots]
    try:
        return questionary.select("Select robot:", choices=names).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _print_robot_summary(robots: list) -> None:  # type: ignore[type-arg]
    typer.echo("")
    for r in robots:
        typer.echo(f"  ● {r['name']}  type={r.get('robot_type', '?')}  lcm={r.get('lcm_url', '?')}")
    typer.echo("")


def _get(path: str) -> list:  # type: ignore[type-arg]
    try:
        resp = httpx.get(f"{DAEMON_URL}{path}", timeout=5.0)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except httpx.ConnectError:
        typer.echo("Harness daemon is not running. Run: dimctl install  (or: dimctl serve)")
        raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
