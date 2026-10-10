"""SuperSeed fork (superseedvc/superseed-internal#10267): the caller's rendered prompt variant.

The lane renders the prompt its bank measured for the broker's model into a JSON file and
names it in SECURITY_SCAN_PROMPT_TEMPLATE. The scanner fills in the pull request, sends the
`system` text as an appended system prompt and the `user` text on stdin, and logs the variant.
Without the variable the scanner's own prompt is sent, unchanged.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claudecode.github_action_audit import SimpleClaudeRunner
from claudecode.prompts import (
    PROMPT_TEMPLATE_ENV,
    get_security_audit_prompt,
    load_prompt_template,
    render_prompt_template,
)

PR = {
    "number": 77,
    "title": "Add {{PR_DIFF}} search",
    "user": "someone",
    "changed_files": 2,
    "additions": 12,
    "deletions": 3,
    "head": {"repo": {"full_name": "owner/repo"}},
    "files": [{"filename": "a.py"}, {"filename": "b/c.ts"}],
}
DIFF = "diff --git a/a.py b/a.py\n+eval(x)\n"

TEMPLATE = {
    "variant": "test-variant",
    "system": "You review pull requests.",
    "user": (
        '<pull_request number="{{PR_NUMBER}}" repository="{{PR_REPO}}" author="{{PR_AUTHOR}}">\n'
        "Title: {{PR_TITLE}}\n"
        "Files changed: {{PR_CHANGED_FILES}}; lines added: {{PR_ADDITIONS}}; lines deleted: {{PR_DELETIONS}}\n"
        "Files modified:\n- {{PR_FILES}}\n</pull_request>\n<pr_diff>\n{{PR_DIFF}}\n</pr_diff>\nReview it."
    ),
}


def write(tmp_path, data):
    p = tmp_path / "prompt.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_render_fills_every_field_in_one_pass(tmp_path):
    t = load_prompt_template(write(tmp_path, TEMPLATE))
    system, user = render_prompt_template(t, PR, DIFF)
    assert system == "You review pull requests."
    assert 'number="77" repository="owner/repo" author="someone"' in user
    assert "Files changed: 2; lines added: 12; lines deleted: 3" in user
    assert "- a.py\n- b/c.ts\n" in user
    assert "<pr_diff>\n" + DIFF + "\n</pr_diff>" in user
    # One pass: a token inside the PR's own title is not substituted again.
    assert "Title: Add {{PR_DIFF}} search" in user
    assert "{{PR_NUMBER}}" not in user


def test_render_without_the_diff_names_the_tools(tmp_path):
    t = load_prompt_template(write(tmp_path, TEMPLATE))
    _, user = render_prompt_template(t, PR, DIFF, include_diff=False)
    assert "eval(x)" not in user
    assert "omitted" in user and "tools" in user


@pytest.mark.parametrize(
    "bad",
    [
        {"system": "s", "user": "{{PR_DIFF}}"},
        {"variant": "v", "system": "", "user": "{{PR_DIFF}}"},
        {"variant": "v", "system": "s", "user": "no diff slot"},
        ["not", "an", "object"],
    ],
)
def test_a_defective_template_is_refused(tmp_path, bad):
    with pytest.raises(ValueError):
        load_prompt_template(write(tmp_path, bad))


def test_a_missing_template_is_refused(tmp_path):
    with pytest.raises((ValueError, OSError)):
        load_prompt_template(str(tmp_path / "absent.json"))


def test_the_runner_appends_the_system_prompt(tmp_path):
    runner = SimpleClaudeRunner()
    ok = MagicMock(returncode=0, stdout=json.dumps({"result": json.dumps({"findings": []})}), stderr="")
    with patch("subprocess.run", return_value=ok) as run:
        success, _, _ = runner.run_security_audit(tmp_path, "the user prompt", system_prompt="the system text")
    assert success
    cmd = run.call_args.args[0]
    assert cmd[cmd.index("--append-system-prompt") + 1] == "the system text"
    assert run.call_args.kwargs["input"] == "the user prompt"


def test_the_runner_without_a_system_prompt_is_unchanged(tmp_path):
    runner = SimpleClaudeRunner()
    ok = MagicMock(returncode=0, stdout=json.dumps({"result": json.dumps({"findings": []})}), stderr="")
    with patch("subprocess.run", return_value=ok) as run:
        runner.run_security_audit(tmp_path, "p")
    assert "--append-system-prompt" not in run.call_args.args[0]


def _main(env, tmp_path):
    """Run main() with every external call mocked, returning (exit code, runner mock, stderr)."""
    from claudecode import github_action_audit as gaa

    runner = MagicMock()
    runner.validate_claude_available.return_value = (True, "")
    runner.run_security_audit.return_value = (True, "", {"findings": []})
    gh = MagicMock()
    gh.get_pr_data.return_value = PR
    gh.get_pr_diff.return_value = DIFF
    full = {"GITHUB_REPOSITORY": "owner/repo", "PR_NUMBER": "77", "GITHUB_TOKEN": "t", "REPO_PATH": str(tmp_path)}
    full.update(env)
    with patch.dict(os.environ, full, clear=False), \
         patch.object(gaa, "DEFAULT_CLAUDE_MODEL", "m"), \
         patch.object(gaa, "initialize_clients", return_value=(gh, runner)), \
         patch.object(gaa, "initialize_findings_filter", return_value=MagicMock()), \
         patch.object(gaa, "apply_findings_filter", return_value=([], [], {})):
        try:
            gaa.main()
            code = 0
        except SystemExit as e:
            code = e.code
    return code, runner


def test_main_sends_the_rendered_variant(tmp_path, capsys):
    code, runner = _main({PROMPT_TEMPLATE_ENV: write(tmp_path, TEMPLATE)}, tmp_path)
    assert code == 0
    kwargs = runner.run_security_audit.call_args.kwargs
    args = runner.run_security_audit.call_args.args
    assert kwargs["system_prompt"] == "You review pull requests."
    assert "eval(x)" in args[1]
    assert "scan prompt: variant test-variant" in capsys.readouterr().err


def test_main_refuses_a_named_template_it_cannot_read(tmp_path, capsys):
    code, runner = _main({PROMPT_TEMPLATE_ENV: str(tmp_path / "absent.json")}, tmp_path)
    assert code != 0
    runner.run_security_audit.assert_not_called()


def test_main_without_a_template_sends_the_scanner_prompt(tmp_path, capsys):
    code, runner = _main({PROMPT_TEMPLATE_ENV: ""}, tmp_path)
    assert code == 0
    assert runner.run_security_audit.call_args.args[1] == get_security_audit_prompt(PR, DIFF)
    assert "system_prompt" not in runner.run_security_audit.call_args.kwargs
    assert "scan prompt: the scanner's own" in capsys.readouterr().err
