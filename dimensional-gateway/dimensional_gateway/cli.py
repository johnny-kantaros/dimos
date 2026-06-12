from __future__ import annotations

import os
import signal
import socket
import threading

import typer

from dimensional_gateway.advertise import GatewayAdvertiser

app = typer.Typer(help="Dimensional Gateway - makes your robot discoverable on the network")


def _robot_name() -> str:
    return os.environ.get("DIMENSIONAL_ROBOT_NAME", socket.gethostname())


def _lcm_url() -> str:
    return os.environ.get("LCM_DEFAULT_URL", "udpm://239.255.76.67:7667?ttl=1")


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
        port=7667,
    )
    advertiser.start()
    typer.echo(f"Advertising {name} at {url}")

    stop_event = threading.Event()

    def _handle_signal(sig: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    stop_event.wait()
    advertiser.stop()
    typer.echo("Gateway stopped")


@app.command()
def install() -> None:
    """Install dimensional-gateway as a login service (starts on boot)."""
    from dimensional_gateway.install import install as _install
    _install()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
