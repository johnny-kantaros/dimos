from __future__ import annotations

from pathlib import Path
import platform
import plistlib
import shlex
import subprocess
import sys

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


def install(env_vars: dict[str, str] | None = None) -> None:
    if platform.system() == "Darwin":
        _install_mac(env_vars or {})
    elif platform.system() == "Linux":
        _install_linux(env_vars or {})
    else:
        print(f"Unsupported platform: {platform.system()}")
        sys.exit(1)


def uninstall() -> None:
    if platform.system() == "Darwin":
        _uninstall_mac()
    elif platform.system() == "Linux":
        _uninstall_linux()


def set_env_var(key: str, value: str) -> None:
    if platform.system() == "Darwin":
        _set_env_var_mac(key, value)
    elif platform.system() == "Linux":
        _set_env_var_linux(key, value)
    else:
        print(f"Unsupported platform: {platform.system()}")


def remove_env_var(key: str) -> None:
    if platform.system() == "Darwin":
        _remove_env_var_mac(key)
    elif platform.system() == "Linux":
        _remove_env_var_linux(key)
    else:
        print(f"Unsupported platform: {platform.system()}")


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


def _install_mac(env_vars: dict[str, str]) -> None:
    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "Label": _LABEL,
        "ProgramArguments": _find_executable(),
        "KeepAlive": True,
        "RunAtLoad": True,
        "StandardOutPath": str(_LOG_PATH),
        "StandardErrorPath": str(_LOG_PATH),
    }
    if env_vars:
        data["EnvironmentVariables"] = env_vars

    _PLIST_PATH.write_bytes(plistlib.dumps(data))
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


def _install_linux(env_vars: dict[str, str]) -> None:
    _SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    exec_start = " ".join(shlex.quote(a) for a in _find_executable())
    all_env = {"PYTHONUNBUFFERED": "1", **env_vars}
    env_lines = "\n".join(f"Environment={k}={v}" for k, v in all_env.items())
    unit = f"""\
[Unit]
Description=Dimensional Gateway
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5
{env_lines}

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


def _reload_mac() -> None:
    subprocess.run(["launchctl", "unload", str(_PLIST_PATH)], capture_output=True)
    result = subprocess.run(
        ["launchctl", "load", "-w", str(_PLIST_PATH)], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Warning: launchctl reload failed: {result.stderr.strip()}")


def _set_env_var_mac(key: str, value: str) -> None:
    if not _PLIST_PATH.exists():
        print("  dimctl is not installed. Run 'dimctl install' first.")
        return
    data = plistlib.loads(_PLIST_PATH.read_bytes())
    env = data.get("EnvironmentVariables", {})
    env[key] = value
    data["EnvironmentVariables"] = env
    _PLIST_PATH.write_bytes(plistlib.dumps(data))
    _reload_mac()
    print(f"  {key} configured. dimctl restarted.")


def _remove_env_var_mac(key: str) -> None:
    if not _PLIST_PATH.exists():
        print("  dimctl is not installed.")
        return
    data = plistlib.loads(_PLIST_PATH.read_bytes())
    env = data.get("EnvironmentVariables", {})
    if key not in env:
        print(f"  {key} is not set.")
        return
    del env[key]
    if env:
        data["EnvironmentVariables"] = env
    else:
        data.pop("EnvironmentVariables", None)
    _PLIST_PATH.write_bytes(plistlib.dumps(data))
    _reload_mac()
    print(f"  {key} removed. dimctl restarted.")


def _set_env_var_linux(key: str, value: str) -> None:
    if not _SYSTEMD_PATH.exists():
        print("  dimctl is not installed. Run 'dimctl install' first.")
        return
    lines = _SYSTEMD_PATH.read_text().splitlines()
    lines = [l for l in lines if not l.startswith(f"Environment={key}=")]
    insert_at = next((i for i, l in enumerate(lines) if l.strip() == "[Install]"), len(lines))
    lines.insert(insert_at, f"Environment={key}={value}")
    _SYSTEMD_PATH.write_text("\n".join(lines) + "\n")
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "restart", "dimensional-gateway"], check=True)
        print(f"  {key} configured. dimctl restarted.")
    except subprocess.CalledProcessError as e:
        print(f"  Failed to restart: {e}")


def _remove_env_var_linux(key: str) -> None:
    if not _SYSTEMD_PATH.exists():
        print("  dimctl is not installed.")
        return
    lines = _SYSTEMD_PATH.read_text().splitlines()
    original = len(lines)
    lines = [l for l in lines if not l.startswith(f"Environment={key}=")]
    if len(lines) == original:
        print(f"  {key} is not set.")
        return
    _SYSTEMD_PATH.write_text("\n".join(lines) + "\n")
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "restart", "dimensional-gateway"], check=True)
        print(f"  {key} removed. dimctl restarted.")
    except subprocess.CalledProcessError as e:
        print(f"  Failed to restart: {e}")
