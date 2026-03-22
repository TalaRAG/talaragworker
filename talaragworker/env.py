from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_if_present() -> None:
    env_path = _find_dotenv_path()
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        name, value = line.split("=", 1)
        key = name.strip()
        if not key:
            continue

        os.environ.setdefault(key, _normalize_env_value(value.strip()))


def _find_dotenv_path() -> Path | None:
    current_path = Path.cwd().resolve()
    for candidate_dir in (current_path, *current_path.parents):
        candidate = candidate_dir / ".env"
        if candidate.is_file():
            return candidate

    return None


def _normalize_env_value(raw_value: str) -> str:
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
        return raw_value[1:-1]

    return raw_value
