"""Rolling-window rate limiter for map refreshes, persisted to a local JSON file."""

import json
import time
from pathlib import Path

STATE_PATH = Path(__file__).parent / ".refresh_state.json"
WINDOW_S = 24 * 60 * 60


def _load(state_path: Path = STATE_PATH):
    if not state_path.exists():
        return {"timestamps": []}
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"timestamps": []}


def check(limit: int, state_path: Path = STATE_PATH):
    """Return (allowed: bool, used: int, limit: int, retry_after_s: float|None)."""
    now = time.time()
    state = _load(state_path)
    recent = [t for t in state["timestamps"] if now - t < WINDOW_S]
    if len(recent) >= limit:
        retry_after = WINDOW_S - (now - min(recent))
        return False, len(recent), limit, retry_after
    return True, len(recent), limit, None


def record(state_path: Path = STATE_PATH):
    now = time.time()
    state = _load(state_path)
    recent = [t for t in state["timestamps"] if now - t < WINDOW_S]
    recent.append(now)
    state_path.write_text(json.dumps({"timestamps": recent}))
    return len(recent)
