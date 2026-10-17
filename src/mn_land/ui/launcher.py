"""Constrained local launcher. CLI/core remain independent of the UI extra."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Command flags outrank global/project config and environment variables. Deliberately
# no bind-host or arbitrary Streamlit flag passthrough. These are not authentication.
LOCAL_OPTIONS = {
    "server.address": "127.0.0.1",
    "browser.serverAddress": "127.0.0.1",
    "browser.gatherUsageStats": "false",
    "server.headless": "true",
    "server.showEmailPrompt": "false",
    "server.enableCORS": "true",
    "server.enableXsrfProtection": "true",
    "server.enableStaticServing": "false",
    "server.fileWatcherType": "none",
    "server.runOnSave": "false",
    "client.toolbarMode": "minimal",
    "client.showErrorDetails": "none",
    "client.disableDataExport": "true",
    "runner.magicEnabled": "false",
}


def arguments(port: int = 8501) -> list[str]:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Port must be an integer from 1 through 65535")
    return [
        "streamlit", "run", str(Path(__file__).with_name("app.py")),
        f"--server.port={port}", f"--browser.serverPort={port}",
        *(f"--{key}={value}" for key, value in LOCAL_OPTIONS.items()),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local land-review selector")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args(argv)
    try:
        launch_args = arguments(args.port)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        from streamlit.web import cli
    except ModuleNotFoundError as exc:
        if exc.name != "streamlit":
            raise
        print('Optional UI missing. Install: python -m pip install -e ".[ui]"', file=sys.stderr)
        return 2
    sys.argv = launch_args
    return cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
