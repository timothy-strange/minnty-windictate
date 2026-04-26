from __future__ import annotations

import json
import os
import signal
import secrets
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing.connection import Client
from pathlib import Path

from .config import SESSION_STATE_PATH, ensure_directories


@dataclass(frozen=True)
class ServiceState:
    pid: int
    port: int
    token: str
    hotkey: str
    cancel_hotkey: str
    started_at: float


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_service_state(path: Path = SESSION_STATE_PATH) -> ServiceState | None:
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
    hotkey = payload.get("hotkey")
    cancel_hotkey = payload.get("cancel_hotkey")
    started_at = payload.get("started_at")
    if not isinstance(pid, int) or not isinstance(port, int) or not isinstance(token, str):
        return None
    if not isinstance(hotkey, str):
        hotkey = ""
    if not isinstance(cancel_hotkey, str):
        cancel_hotkey = ""
    if not isinstance(started_at, (int, float)):
        started_at = time.time()
    return ServiceState(
        pid=pid,
        port=port,
        token=token,
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        started_at=float(started_at),
    )


def write_service_state(state: ServiceState, path: Path = SESSION_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


def clear_service_state(path: Path = SESSION_STATE_PATH) -> None:
    path.unlink(missing_ok=True)


def service_is_running(path: Path = SESSION_STATE_PATH) -> bool:
    state = read_service_state(path)
    return state is not None and process_is_running(state.pid)


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _connect(state: ServiceState):
    return Client(("127.0.0.1", state.port), authkey=state.token.encode("utf-8"))


def _shutdown_existing_service(state: ServiceState, path: Path = SESSION_STATE_PATH) -> None:
    _request_shutdown(state)
    _wait_for_service_exit(state, path=path)


def _request_shutdown(state: ServiceState) -> None:
    try:
        with _connect(state) as conn:
            conn.send({"action": "shutdown"})
            _response = conn.recv()
    except OSError:
        pass


def _wait_for_service_exit(state: ServiceState, *, path: Path = SESSION_STATE_PATH) -> None:
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not process_is_running(state.pid):
            clear_service_state(path)
            return
        time.sleep(0.1)
    try:
        os.kill(state.pid, signal.SIGTERM)
    except OSError:
        clear_service_state(path)
        return
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if not process_is_running(state.pid):
            clear_service_state(path)
            return
        time.sleep(0.1)
    clear_service_state(path)
    raise RuntimeError("Resident service did not stop in time and could not be terminated.")


def wait_for_service_ready(state: ServiceState, *, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process_is_running(state.pid):
            clear_service_state()
            raise RuntimeError("Resident service exited during startup.")
        try:
            with _connect(state) as conn:
                conn.send({"action": "ping"})
                response = conn.recv()
        except OSError:
            time.sleep(0.1)
            continue
        if response == {"ok": True, "status": "ready"}:
            return
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for resident service.")


def start_service(hotkey: str, cancel_hotkey: str, path: Path = SESSION_STATE_PATH) -> ServiceState:
    existing = read_service_state(path)
    if existing is not None and process_is_running(existing.pid):
        if existing.hotkey == hotkey and existing.cancel_hotkey == cancel_hotkey:
            return existing
        _shutdown_existing_service(existing, path)
    clear_service_state(path)
    ensure_directories()
    port = _reserve_port()
    token = secrets.token_hex(16)
    command = [
        sys.executable,
        "-m",
        "minnty_windictate.cli",
        "service",
        "--port",
        str(port),
        "--token",
        token,
        "--hotkey",
        hotkey,
        "--cancel-hotkey",
        cancel_hotkey,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, creationflags=creationflags)
    state = ServiceState(
        pid=process.pid,
        port=port,
        token=token,
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        started_at=time.time(),
    )
    write_service_state(state, path)
    wait_for_service_ready(state)
    return state


def ensure_service(hotkey: str, cancel_hotkey: str, *, autostart: bool) -> ServiceState:
    state = read_service_state()
    if state is not None and process_is_running(state.pid):
        return state
    if not autostart:
        raise RuntimeError("Resident service is not running.")
    return start_service(hotkey, cancel_hotkey)


def send_service_command(
    action: str,
    *,
    hotkey: str,
    cancel_hotkey: str,
    autostart: bool,
    **payload: object,
) -> dict:
    state = ensure_service(hotkey, cancel_hotkey, autostart=autostart)
    try:
        with _connect(state) as conn:
            conn.send({"action": action, **payload})
            response = conn.recv()
    except OSError as exc:
        clear_service_state()
        if autostart:
            state = start_service(hotkey, cancel_hotkey)
            with _connect(state) as conn:
                conn.send({"action": action, **payload})
                response = conn.recv()
        else:
            raise RuntimeError(f"Resident service connection failed: {exc}") from exc
    if not isinstance(response, dict):
        raise RuntimeError("Resident service returned an invalid response.")
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error", "Resident service request failed.")))
    return response


def stop_service(hotkey: str, cancel_hotkey: str) -> str:
    state = read_service_state()
    if state is None or not process_is_running(state.pid):
        clear_service_state()
        return "Resident service is not running"
    response = send_service_command(
        "shutdown",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=False,
    )
    _wait_for_service_exit(state)
    return str(response.get("message", "Resident service stopped"))
