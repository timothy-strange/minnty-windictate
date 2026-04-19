from __future__ import annotations

import sys

APP_NAME = "minnty-windictate"


def notify(title: str, message: str) -> None:
    try:
        from win10toast import ToastNotifier

        ToastNotifier().show_toast(title, message, duration=3, threaded=True)
        return
    except Exception:
        pass

    print(f"[{title}] {message}", file=sys.stderr)
