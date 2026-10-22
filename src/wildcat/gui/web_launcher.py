"""Open the web UI in the default browser."""

import webbrowser


def open_web_ui(url: str = "http://127.0.0.1:8000") -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001
        return False
