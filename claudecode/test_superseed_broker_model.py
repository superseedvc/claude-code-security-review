"""SuperSeed fork: the model comes from the caller's broker read, and no model id is compiled in."""

import json
import os
import pathlib
import re
import subprocess
import sys
from unittest.mock import MagicMock

from claudecode.claude_api_client import ClaudeAPIClient

PKG = pathlib.Path(__file__).resolve().parent


def test_validation_probe_uses_the_configured_model():
    client = ClaudeAPIClient.__new__(ClaudeAPIClient)
    client.model = "broker-assigned-model"
    client.client = MagicMock()
    ok, err = client.validate_api_access()
    assert ok, err
    assert client.client.messages.create.call_args.kwargs["model"] == "broker-assigned-model"


def _constants(env):
    code = "import json; from claudecode import constants as c; print(json.dumps([c.DEFAULT_CLAUDE_MODEL, c.FILTER_CLAUDE_MODEL]))"
    full = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_MODEL", "CLAUDE_FILTER_MODEL")}
    full.update(env)
    out = subprocess.run([sys.executable, "-c", code], env=full, cwd=PKG.parent, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_filter_model_follows_the_scan_model_unless_set_apart():
    assert _constants({"CLAUDE_MODEL": "m-scan"}) == ["m-scan", "m-scan"]
    assert _constants({"CLAUDE_MODEL": "m-scan", "CLAUDE_FILTER_MODEL": "m-filter"}) == ["m-scan", "m-filter"]
    assert _constants({"CLAUDE_MODEL": "m-scan", "CLAUDE_FILTER_MODEL": ""}) == ["m-scan", "m-scan"]
    assert _constants({}) == ["", ""]


def test_main_refuses_without_a_model():
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_MODEL", "CLAUDE_FILTER_MODEL")}
    env.update({"GITHUB_REPOSITORY": "o/r", "PR_NUMBER": "1", "GITHUB_TOKEN": "t"})
    r = subprocess.run([sys.executable, "-m", "claudecode.github_action_audit"], env=env, cwd=PKG.parent, capture_output=True, text=True)
    assert r.returncode == 2
    assert "CLAUDE_MODEL is not set" in r.stdout


def test_no_model_id_is_compiled_into_the_runtime_code():
    rx = re.compile(r"claude-(?:\d|opus|sonnet|haiku)[\w.-]*-20\d{6}")
    for f in PKG.glob("*.py"):
        if f.name.startswith("test_"):
            continue
        assert not rx.search(f.read_text()), f"{f.name} carries a dated model id"
