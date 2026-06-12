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
        bp = r.get("blueprint") or "—"
        typer.echo(f"  {r['name']}  [{r['status']}]  type={r['robot_type']}  blueprint={bp}")
        typer.echo(f"    lcm: {r['lcm_url']}  addr: {r['address']}")


@app.command(name="list-sessions")
def list_sessions() -> None:
    """List active sessions."""
    sessions = _get("/sessions")
    if not sessions:
        typer.echo("No active sessions.")
        return
    for s in sessions:
        typer.echo(f"  {s['session_id']}  robot={s['robot_name']}")


@app.command()
def chat(
    robot: str | None = typer.Option(None, "--robot", "-r", help="Robot name to connect to"),
) -> None:
    """Chat with a robot."""
    robots = _get("/robots")

    if not robots:
        typer.echo("No robots found on the network. Is dimensional-gateway running?")
        raise typer.Exit(1)

    if robot is None:
        if len(robots) == 1:
            robot = robots[0]["name"]
        else:
            typer.echo("Multiple robots found. Pick one with --robot:")
            for r in robots:
                typer.echo(f"  {r['name']}  [{r['status']}]")
            raise typer.Exit(1)

    resp = httpx.post(f"{DAEMON_URL}/sessions", json={"robot_name": robot}, timeout=10.0)
    if resp.status_code == 404:
        typer.echo(f"Robot {robot!r} not found.")
        raise typer.Exit(1)
    if resp.status_code == 503:
        typer.echo(f"Robot {robot!r} is unreachable: {resp.json().get('detail')}")
        raise typer.Exit(1)
    resp.raise_for_status()

    session_id = resp.json()["session_id"]
    typer.echo(f"Session started with {robot}. Type a message, or 'exit' to quit.\n")

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
