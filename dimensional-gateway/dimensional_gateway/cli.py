from __future__ import annotations

import hashlib
import os
import signal
import socket
import threading
from typing import Any

import typer

from dimensional_gateway.advertise import GatewayAdvertiser
from dimensional_gateway.watcher import _current_entry, watch

app = typer.Typer(help="Dimensional Gateway - makes your robot discoverable on the network")


def _robot_name() -> str:
    return os.environ.get("DIMENSIONAL_ROBOT_NAME", socket.gethostname())


def _assigned_port() -> int:
    """Deterministic port derived from hostname — unique per robot, stable across reinstalls."""
    hostname = socket.gethostname()
    return 7667 + (int(hashlib.md5(hostname.encode()).hexdigest()[:4], 16) % 1000)


def _lcm_url() -> str:
    raw = os.environ.get("LCM_DEFAULT_URL", f"udpm://239.255.76.67:{_assigned_port()}?ttl=1")
    # ensure ttl>=1 so packets cross the network
    if "ttl=0" in raw:
        raw = raw.replace("ttl=0", "ttl=1")
    elif "ttl=" not in raw:
        sep = "&" if "?" in raw else "?"
        raw = f"{raw}{sep}ttl=1"
    return raw


@app.command()
def serve(
    robot_type: str = typer.Option("unknown", "--robot-type", help="Robot type (e.g. go2, spot)"),
    version: str = typer.Option("0.1.0", "--version", help="Software version"),
) -> None:
    """Advertise this robot on the local network via mDNS."""
    name = _robot_name()
    url = _lcm_url()

    advertiser = GatewayAdvertiser(
        robot_name=name,
        lcm_url=url,
        robot_type=robot_type,
        version=version,
        port=_assigned_port(),
    )
    advertiser.start()
    typer.echo(f"Advertising {name} at {url}")

    import uvicorn
    from dimensional_gateway.server import HTTP_PORT, app as gateway_app

    http_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": gateway_app, "host": "0.0.0.0", "port": HTTP_PORT, "log_level": "error"},
        daemon=True,
    )
    http_thread.start()
    typer.echo(f"Gateway API on port {HTTP_PORT}")

    stop_event = threading.Event()

    def _on_change(entry: dict[str, Any] | None) -> None:
        advertiser.update(entry)
        if entry:
            typer.echo(f"DIMOS running: {entry.get('blueprint', '?')}")
        else:
            typer.echo("DIMOS idle")

    def _handle_signal(sig: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        watch(on_change=_on_change, stop_event=stop_event)
    finally:
        advertiser.stop()
        typer.echo("Gateway stopped")


@app.command()
def install() -> None:
    """Install dimensional-gateway as a systemd user service."""
    from dimensional_gateway.install import install as _install
    _install()


@app.command()
def status() -> None:
    """Show current gateway and DIMOS status."""
    name = _robot_name()
    url = _lcm_url()
    entry = _current_entry()

    typer.echo(f"Robot:   {name}")
    typer.echo(f"LCM URL: {url}")
    if entry:
        typer.echo(f"DIMOS:   running — {entry.get('blueprint', '?')} (pid {entry.get('pid')})")
    else:
        typer.echo("DIMOS:   idle")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
