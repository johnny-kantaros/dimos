from __future__ import annotations

import json
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_REGISTRY_DIR = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
) / "dimos" / "runs"

_POLL_INTERVAL = 2.0


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists but we can't signal it


def _current_entry() -> dict[str, Any] | None:
    if not _REGISTRY_DIR.exists():
        return None
    entries = []
    for path in sorted(_REGISTRY_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            if _is_pid_alive(data["pid"]):
                entries.append(data)
        except Exception:
            continue
    return entries[-1] if entries else None


def watch(on_change: Callable[[dict[str, Any] | None], None], stop_event: Any) -> None:
    """Poll the run registry and call on_change when DIMOS starts or stops."""
    last: dict[str, Any] | None = _current_entry()
    on_change(last)

    while not stop_event.is_set():
        time.sleep(_POLL_INTERVAL)
        current = _current_entry()
        if _state_changed(last, current):
            on_change(current)
            last = current


def _state_changed(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    if (a is None) != (b is None):
        return True
    if a is None or b is None:
        return False
    return a.get("run_id") != b.get("run_id") or a.get("blueprint") != b.get("blueprint")
