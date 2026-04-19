from __future__ import annotations

import json
import secrets
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing.connection import Client
from pathlib import Path

from .config import SESSION_STATE_PATH, SessionConfig, ensure_directories
from .recording_state import process_is_running


@dataclass(frozen=True)
class SessionState:
    pid: int
    port: int
    token: str
    started_at: float


def read_session_state(path: Path = SESSION_STATE_PATH) -> SessionState | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    port = payload.get("port")
    token = payload.get("token")
    started_at = payload.get("started_at")
    if not isinstance(pid, int) or not isinstance(port, int) or not isinstance(token, str):
        return None
    if not isinstance(started_at, (int, float)):
        started_at = time.time()
    return SessionState(
        pid=pid,
        port=port,
        token=token,
        started_at=float(started_at),
    )


def write_session_state(state: SessionState, path: Path = SESSION_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


def clear_session_state(path: Path = SESSION_STATE_PATH) -> None:
    path.unlink(missing_ok=True)


def reserve_session_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def session_is_running(path: Path = SESSION_STATE_PATH) -> bool:
    state = read_session_state(path)
    return state is not None and process_is_running(state.pid)


def start_session_server(session: SessionConfig, path: Path = SESSION_STATE_PATH) -> SessionState:
    existing = read_session_state(path)
    if existing is not None and process_is_running(existing.pid):
        return existing

    clear_session_state(path)
    ensure_directories()
    port = reserve_session_port()
    token = secrets.token_hex(16)
    command = [
        sys.executable,
        "-m",
        "minnty_windictate.cli",
        "session-server",
        "--port",
        str(port),
        "--token",
        token,
        "--model-name",
        session.model_name,
        "--device",
        session.device,
        "--compute-type",
        session.compute_type,
        "--beam-size",
        str(session.beam_size),
    ]
    if session.language:
        command.extend(["--language", session.language])

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, creationflags=creationflags)
    state = SessionState(
        pid=process.pid,
        port=port,
        token=token,
        started_at=time.time(),
    )
    write_session_state(state, path)
    wait_for_session_ready(state)
    return state


def connect_to_session(state: SessionState):
    return Client(("127.0.0.1", state.port), authkey=state.token.encode("utf-8"))


def wait_for_session_ready(state: SessionState, *, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process_is_running(state.pid):
            clear_session_state()
            raise RuntimeError("Session server exited during startup.")
        try:
            with connect_to_session(state) as conn:
                conn.send({"action": "ping"})
                response = conn.recv()
        except OSError:
            time.sleep(0.1)
            continue
        if response == {"ok": True, "status": "ready"}:
            return
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for session server.")


def ensure_session_server(session: SessionConfig) -> SessionState:
    state = read_session_state()
    if state is None or not process_is_running(state.pid):
        return start_session_server(session)
    return state


def transcribe_via_session(path: Path, session: SessionConfig) -> str:
    state = ensure_session_server(session)
    with connect_to_session(state) as conn:
        conn.send({"action": "transcribe", "path": str(path)})
        response = conn.recv()
    if not isinstance(response, dict) or not response.get("ok"):
        raise RuntimeError(str(response.get("error", "Session transcription failed.")))
    return str(response.get("text", ""))


def stop_session_server(path: Path = SESSION_STATE_PATH) -> str:
    state = read_session_state(path)
    if state is None:
        return "Session is not running"
    if not process_is_running(state.pid):
        clear_session_state(path)
        return "Session is not running"
    try:
        with connect_to_session(state) as conn:
            conn.send({"action": "shutdown"})
            _response = conn.recv()
    except OSError:
        pass
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not process_is_running(state.pid):
            clear_session_state(path)
            return "Session stopped"
        time.sleep(0.1)
    raise RuntimeError("Session server did not stop in time.")
