from __future__ import annotations

from pathlib import Path
import platform
import shlex
import subprocess
import sys
from xml.sax.saxutils import escape

_LABEL = "com.dimensional.gateway"
_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"
_SYSTEMD_PATH = Path.home() / ".config" / "systemd" / "user" / "dimensional-gateway.service"
_LOG_PATH = Path.home() / "Library" / "Logs" / "dimensional-gateway.log"


def is_installed() -> bool:
    if platform.system() == "Darwin":
        return _PLIST_PATH.exists()
    if platform.system() == "Linux":
        return _SYSTEMD_PATH.exists()
    return False


def install() -> None:
    if platform.system() == "Darwin":
        _install_mac()
    elif platform.system() == "Linux":
        _install_linux()
    else:
        print(f"Unsupported platform: {platform.system()}")
        sys.exit(1)


def uninstall() -> None:
    if platform.system() == "Darwin":
        _uninstall_mac()
    elif platform.system() == "Linux":
        _uninstall_linux()


def restart() -> None:
    if platform.system() == "Darwin":
        stop = subprocess.run(["launchctl", "stop", _LABEL], capture_output=True)
        start = subprocess.run(["launchctl", "start", _LABEL], capture_output=True)
        if stop.returncode != 0 or start.returncode != 0:
            print("  Failed to restart (is the service installed?)")
        else:
            print("  dimctl restarted.")
    elif platform.system() == "Linux":
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", "dimensional-gateway"], check=True
            )
            print("  dimctl restarted.")
        except subprocess.CalledProcessError as e:
            print(f"  Failed to restart: {e}")


def _find_executable() -> list[str]:
    return [sys.executable, "-m", "dimensional_gateway"]


def _install_mac() -> None:
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    args = "\n".join(f"        <string>{escape(a)}</string>" for a in _find_executable())
    plist = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{args}
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{escape(str(_LOG_PATH))}</string>
    <key>StandardErrorPath</key>
    <string>{escape(str(_LOG_PATH))}</string>
</dict>
</plist>
"""
    _PLIST_PATH.write_text(plist)
    subprocess.run(["launchctl", "unload", str(_PLIST_PATH)], capture_output=True)
    result = subprocess.run(
        ["launchctl", "load", "-w", str(_PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Warning: launchctl load failed: {result.stderr.strip()}")
        _PLIST_PATH.unlink(missing_ok=True)
    else:
        print(f"  dimctl installed — logs at {_LOG_PATH}")


def _uninstall_mac() -> None:
    if not _PLIST_PATH.exists():
        print("  dimctl is not installed (run 'dimctl install' to set up the service).")
        return
    subprocess.run(["launchctl", "unload", "-w", str(_PLIST_PATH)], capture_output=True)
    _PLIST_PATH.unlink()
    print("  dimctl removed.")


def _install_linux() -> None:
    _SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    exec_start = " ".join(shlex.quote(a) for a in _find_executable())
    unit = f"""\
[Unit]
Description=Dimensional Gateway
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""
    _SYSTEMD_PATH.write_text(unit)
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "dimensional-gateway"], check=True
        )
        print("  dimctl installed.")
    except FileNotFoundError:
        print(f"  systemctl not found — start manually: {exec_start}")
        _SYSTEMD_PATH.unlink(missing_ok=True)
    except subprocess.CalledProcessError as e:
        print(f"  Failed to enable service: {e}")
        _SYSTEMD_PATH.unlink(missing_ok=True)


def _uninstall_linux() -> None:
    if not _SYSTEMD_PATH.exists():
        print("  dimctl is not installed (run 'dimctl install' to set up the service).")
        return
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "dimensional-gateway"], check=True
        )
    except subprocess.CalledProcessError:
        pass
    _SYSTEMD_PATH.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print("  dimctl removed.")
