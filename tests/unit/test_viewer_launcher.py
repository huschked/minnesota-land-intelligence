"""Optional launch configuration and dependency boundary, no live server."""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from mn_land.ui.launcher import LOCAL_OPTIONS, arguments


@pytest.mark.parametrize("port", [0, 65536, True, "8501", -1])
def test_invalid_ports_rejected(port):
    with pytest.raises(ValueError):
        arguments(port)


def test_launch_cannot_bind_publicly_or_forward_arbitrary_flags():
    args = arguments(18502)
    assert "--server.address=127.0.0.1" in args
    assert "--server.port=18502" in args
    assert "--browser.gatherUsageStats=false" in args
    assert "--server.showEmailPrompt=false" in args
    assert "--server.enableStaticServing=false" in args
    assert "--server.enableCORS=true" in args
    assert "--server.enableXsrfProtection=true" in args
    assert args[2].endswith("app.py")


def test_project_config_matches_forced_launcher_settings():
    path = Path(__file__).parents[2] / ".streamlit/config.toml"
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    for name, value in LOCAL_OPTIONS.items():
        group, key = name.split(".")
        expected = value if value not in ("true", "false") else value == "true"
        assert payload[group][key] == expected


@pytest.mark.ui
def test_installed_version_accepts_every_security_option_and_uses_cli_precedence():
    pytest.importorskip("streamlit")
    # A fresh process avoids AppTest's already-loaded config and applies real CLI
    # precedence over intentionally unsafe environment values without starting a server.
    program = '''
import json, os
from streamlit import config
from mn_land.ui.launcher import LOCAL_OPTIONS
os.environ["STREAMLIT_SERVER_ADDRESS"] = "0.0.0.0"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "true"
values = {key: value if value not in ("true", "false") else value == "true"
          for key, value in LOCAL_OPTIONS.items()}
config.get_config_options(force_reparse=True, options_from_flags=values)
print(json.dumps({key: config.get_option(key) for key in values}))
'''
    result = subprocess.run(
        [sys.executable, "-c", program], check=False, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual == {
        key: value if value not in ("true", "false") else value == "true"
        for key, value in LOCAL_OPTIONS.items()
    }
