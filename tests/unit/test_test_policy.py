"""Exercise the real pytest configuration without contacting a county service."""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("explicit_integration", [False, True])
def test_default_selection_and_explicit_integration_override(
    tmp_path: Path, explicit_integration: bool,
) -> None:
    # Reuse the repository configuration, not a hardcoded copy of its options.
    (tmp_path / "pyproject.toml").write_bytes((PROJECT_ROOT / "pyproject.toml").read_bytes())
    tests = tmp_path / "tests"
    tests.mkdir()
    # The deselected test fails if selection regresses; neither test uses a network.
    (tests / "test_selection.py").write_text(
        "import pytest\n"
        f"def test_offline():\n    assert {not explicit_integration!r}\n"
        "@pytest.mark.integration\n"
        f"def test_live_sentinel():\n    assert {explicit_integration!r}\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    arguments = ["-m", "integration"] if explicit_integration else []
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *arguments],
        check=False, cwd=tmp_path, env=environment, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 deselected" in result.stdout


@pytest.mark.parametrize("operation", ["resolve", "create_connection", "connect", "connect_ex"])
def test_offline_guard_blocks_network_before_contact(operation: str) -> None:
    with (
        socket.socket() as connection,
        pytest.raises(pytest.fail.Exception, match="Network access is disabled"),
    ):
        if operation == "resolve":
            socket.getaddrinfo("example.test", 443)
        elif operation == "create_connection":
            socket.create_connection(("example.test", 443))
        elif operation == "connect":
            connection.connect(("127.0.0.1", 443))
        else:
            connection.connect_ex(("127.0.0.1", 443))
