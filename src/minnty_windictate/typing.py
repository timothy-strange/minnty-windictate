from __future__ import annotations

import keyboard


def type_text(text: str) -> None:
    if not text:
        return
    keyboard.write(text, delay=0.001)
