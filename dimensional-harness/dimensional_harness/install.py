from __future__ import annotations

import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

_LABEL = "com.dimensional.harness"
_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"
_SYSTEMD_PATH = Path.home() / ".config" / "systemd" / "user" / "dimensional-harness.service"
_LOG_PATH = Path.home() / "Library" / "Logs" / "dimensional-harness.log"


def install() -> None:
    executable = _find_executable()
    if platform.system() == "Darwin":
        _install_mac(executable)
    elif platform.system() == "Linux":
        _install_linux(executable)
    else:
        print(f"Unsupported platform: {platform.system()}")
        sys.exit(1)


def restart() -> None:
    if platform.system() == "Darwin":
        _restart_mac()
    elif platform.system() == "Linux":
        _restart_linux()
    else:
        print(f"Unsupported platform: {platform.system()}")
        sys.exit(1)


def uninstall() -> None:
    if platform.system() == "Darwin":
        _uninstall_mac()
    elif platform.system() == "Linux":
        _uninstall_linux()
    else:
        print(f"Unsupported platform: {platform.system()}")
        sys.exit(1)


# ── Mac ───────────────────────────────────────────────────────────────────────

def _install_mac(executable: str) -> None:
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

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
        <string>{executable}</string>
        <string>serve</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{_LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>{_LOG_PATH}</string>
</dict>
</plist>
"""
    _PLIST_PATH.write_text(plist)

    # Unload first in case an old version is already loaded
    subprocess.run(
        ["launchctl", "unload", str(_PLIST_PATH)],
        capture_output=True,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(_PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Warning: launchctl load failed: {result.stderr.strip()}")
        print(f"You can load it manually: launchctl load -w {_PLIST_PATH}")
    else:
        print(f"Installed: {_PLIST_PATH}")
        print(f"Logs:      {_LOG_PATH}")
        print("dimctl will start on login and restart on crash.")
        print("To stop:   dimctl uninstall")


def _restart_mac() -> None:
    if not _PLIST_PATH.exists():
        print("Not installed. Run: dimctl install")
        sys.exit(1)
    subprocess.run(["launchctl", "stop", _LABEL], capture_output=True)
    subprocess.run(["launchctl", "start", _LABEL], capture_output=True)
    print("dimctl daemon restarted.")


def _restart_linux() -> None:
    try:
        subprocess.run(
            ["systemctl", "--user", "restart", "dimensional-harness"], check=True
        )
        print("dimctl daemon restarted.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart: {e}")


def _uninstall_mac() -> None:
    if not _PLIST_PATH.exists():
        print("Not installed.")
        return
    subprocess.run(["launchctl", "unload", "-w", str(_PLIST_PATH)], capture_output=True)
    _PLIST_PATH.unlink()
    print(f"Removed {_PLIST_PATH}")
    print("dimctl will no longer start on login.")


# ── Linux ─────────────────────────────────────────────────────────────────────

def _install_linux(executable: str) -> None:
    _SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    unit = f"""\
[Unit]
Description=Dimensional Harness
After=network.target

[Service]
Type=simple
ExecStart={executable} serve
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
            ["systemctl", "--user", "enable", "--now", "dimensional-harness"],
            check=True,
        )
        print(f"Installed: {_SYSTEMD_PATH}")
        print("dimctl will start on login and restart on crash.")
        print("To stop:   dimctl uninstall")
    except FileNotFoundError:
        print("systemctl not found.")
        print(f"Start manually: {executable} serve")
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable service: {e}")
        print(f"Enable manually: systemctl --user enable --now dimensional-harness")


def _uninstall_linux() -> None:
    if not _SYSTEMD_PATH.exists():
        print("Not installed.")
        return
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "dimensional-harness"],
            check=True,
        )
    except subprocess.CalledProcessError:
        pass
    _SYSTEMD_PATH.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print(f"Removed {_SYSTEMD_PATH}")
    print("dimctl will no longer start on login.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_executable() -> str:
    # Prefer the installed entry point on PATH
    found = shutil.which("dimctl")
    if found:
        return found
    # Fall back to invoking the module via the current interpreter
    return f"{sys.executable} -m dimensional_harness.cli"
