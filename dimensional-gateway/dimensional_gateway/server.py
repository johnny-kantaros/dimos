from __future__ import annotations

import os
import shutil
import signal
import subprocess
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dimensional_gateway.watcher import _current_entry, _is_pid_alive

HTTP_PORT = 8129

app = FastAPI(title="Dimensional Gateway", version="0.1.0")


class StartRequest(BaseModel):
    blueprint: str


@app.get("/status")
def status() -> dict[str, Any]:
    entry = _current_entry()
    if entry:
        return {"status": "running", "blueprint": entry.get("blueprint", ""), "pid": entry.get("pid")}
    return {"status": "idle", "blueprint": "", "pid": None}


@app.post("/start")
def start(body: StartRequest) -> dict[str, str]:
    entry = _current_entry()
    if entry:
        return {"status": "already_running", "blueprint": entry.get("blueprint", "")}
    dimos_exe = shutil.which("dimos")
    if not dimos_exe:
        raise HTTPException(503, "dimos not found on PATH — is it installed?")
    from dimensional_gateway.cli import _lcm_url
    env = {**os.environ, "LCM_DEFAULT_URL": _lcm_url()}
    proc = subprocess.Popen(
        [dimos_exe, "run", body.blueprint],
        start_new_session=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        proc.stdin.write(b"y\ny\ny\ny\n")  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]
    except OSError:
        pass
    return {"status": "starting", "blueprint": body.blueprint}


@app.get("/blueprints")
def list_blueprints() -> dict[str, Any]:
    dimos_exe = shutil.which("dimos")
    if not dimos_exe:
        raise HTTPException(503, "dimos not found on PATH — is it installed?")
    result = subprocess.run([dimos_exe, "list"], capture_output=True, text=True, timeout=10)
    blueprints = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {"blueprints": blueprints}


@app.post("/stop")
def stop() -> dict[str, str]:
    entry = _current_entry()
    if entry is None:
        raise HTTPException(404, "No running DIMOS instance")
    try:
        os.kill(entry["pid"], signal.SIGTERM)
        return {"status": "stopping", "pid": str(entry["pid"])}
    except ProcessLookupError:
        raise HTTPException(404, "Process already gone")
