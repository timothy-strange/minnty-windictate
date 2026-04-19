from __future__ import annotations

import argparse
from multiprocessing.connection import Listener

from .config import SessionConfig
from .transcribe import build_model, transcribe_file


def serve_session(*, port: int, token: str, session: SessionConfig) -> None:
    model = build_model(session)
    listener = Listener(("127.0.0.1", port), authkey=token.encode("utf-8"))
    try:
        running = True
        while running:
            with listener.accept() as conn:
                request = conn.recv()
                action = request.get("action") if isinstance(request, dict) else None
                if action == "ping":
                    conn.send({"ok": True, "status": "ready"})
                    continue
                if action == "transcribe":
                    path = request.get("path")
                    if not isinstance(path, str):
                        conn.send({"ok": False, "error": "Missing path"})
                        continue
                    try:
                        text = transcribe_file(path, model=model, session=session)
                    except Exception as exc:
                        conn.send({"ok": False, "error": str(exc)})
                        continue
                    conn.send({"ok": True, "text": text})
                    continue
                if action == "shutdown":
                    conn.send({"ok": True})
                    running = False
                    continue
                conn.send({"ok": False, "error": "Unknown action"})
    finally:
        listener.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minnty-windictate-session")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--compute-type", required=True)
    parser.add_argument("--beam-size", type=int, required=True)
    parser.add_argument("--language")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    serve_session(
        port=args.port,
        token=args.token,
        session=SessionConfig(
            model_name=args.model_name,
            device=args.device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            language=args.language,
        ),
    )


if __name__ == "__main__":
    main()
