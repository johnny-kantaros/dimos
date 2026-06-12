from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dimensional_gateway.cli import _lcm_url, _robot_name


def install() -> None:
    unit_path = _write_systemd_unit()
    _enable_service(unit_path)
    print(f"Robot:   {_robot_name()}")
    print(f"LCM URL: {_lcm_url()}")
    print(f"Installed: {unit_path}")
    print("dimensional-gateway will start on boot and restart on failure.")
    print("Run: systemctl --user status dimensional-gateway")


def _write_systemd_unit() -> Path:
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    unit_path = systemd_dir / "dimensional-gateway.service"

    unit = f"""\
[Unit]
Description=Dimensional Gateway
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} -m dimensional_gateway.cli serve
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""
    unit_path.write_text(unit)
    return unit_path


def _enable_service(unit_path: Path) -> None:
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "dimensional-gateway"], check=True)
    except FileNotFoundError:
        print("systemctl not found — skipping service enable (not on Linux?)")
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable service: {e}")
        print(f"Enable manually: systemctl --user enable --now {unit_path}")
