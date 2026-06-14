from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_SKILLS_DIR = Path(__file__).parent / "skills"
_ROBOT_SKILLS_DIR = _SKILLS_DIR / "robots"


def _system_path(name: str) -> Path:
    return _SKILLS_DIR / f"{name}.yaml"


def _robot_path(name: str, robot: str) -> Path:
    return _ROBOT_SKILLS_DIR / robot / f"{name}.yaml"


def _read_description(path: Path) -> str:
    try:
        data = yaml.safe_load(path.read_text())
        return data.get("description", "") if isinstance(data, dict) else ""
    except Exception:
        return ""


def _format_skill(data: dict[str, Any]) -> str:
    parts = [f"Description: {data['description']}"]
    if instructions := data.get("instructions"):
        parts += ["", "Instructions:", instructions.strip()]
    if steps := data.get("steps"):
        parts.append("")
        parts.append("Steps:")
        for i, step in enumerate(steps, 1):
            parts.append(f"{i}. {step}")
    return "\n".join(parts)


def list_skills(robot: str) -> dict[str, str]:
    """Return {name: description}, robot-specific skills overlaid on system skills."""
    skills: dict[str, str] = {}
    for path in sorted(_SKILLS_DIR.glob("*.yaml")):
        skills[path.stem] = _read_description(path)
    robot_dir = _ROBOT_SKILLS_DIR / robot
    if robot_dir.exists():
        for path in sorted(robot_dir.glob("*.yaml")):
            skills[path.stem] = _read_description(path)
    return skills


def load_skill(name: str, robot: str) -> str | None:
    path = _robot_path(name, robot)
    if path.exists():
        return _format_skill(yaml.safe_load(path.read_text()))
    path = _system_path(name)
    if not path.exists():
        return None
    return _format_skill(yaml.safe_load(path.read_text()))


def save_skill(name: str, data: dict[str, Any], robot: str | None = None) -> None:
    path = _robot_path(name, robot) if robot else _system_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
