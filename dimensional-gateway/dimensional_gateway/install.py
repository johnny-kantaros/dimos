from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dimensional_gateway.cli import _assigned_port, _lcm_url, _robot_name


def install() -> None:
    lcm_url = _lcm_url()
    _write_lcm_env(lcm_url)
    unit_path = _write_systemd_unit()
    _enable_service(unit_path)
    print(f"Robot:   {_robot_name()}")
    print(f"LCM URL: {lcm_url}  (port {_assigned_port()})")
    print(f"Installed: {unit_path}")
    print("dimensional-gateway will start on boot and restart on failure.")
    print("Run: systemctl --user status dimensional-gateway")


def _write_lcm_env(lcm_url: str) -> None:
    """Write LCM_DEFAULT_URL to /etc/environment so DIMOS inherits it on startup."""
    env_path = Path("/etc/environment")
    try:
        lines = env_path.read_text().splitlines() if env_path.exists() else []
        lines = [l for l in lines if not l.startswith("LCM_DEFAULT_URL=")]
        lines.append(f"LCM_DEFAULT_URL={lcm_url}")
        env_path.write_text("\n".join(lines) + "\n")
    except PermissionError:
        print(f"Note: could not write to /etc/environment (need sudo).")
        print(f"Set manually: LCM_DEFAULT_URL={lcm_url}")


def _write_systemd_unit() -> Path:
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    unit_path = systemd_dir / "dimensional-gateway.service"

    executable = sys.executable
    unit = f"""\
[Unit]
Description=Dimensional Gateway
After=network.target

[Service]
Type=simple
ExecStart={executable} -m dimensional_gateway.cli serve
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
        print(f"You can enable it manually:\n  systemctl --user enable --now {unit_path}")
