"""superseedvc/superseed-internal#9380: a 406 from the diff endpoint builds the diff from git."""

import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from claudecode.github_action_audit import AuditError, GitHubActionClient


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, 'init', '-q')
    _git(tmp_path, 'config', 'user.email', 't@example.invalid')
    _git(tmp_path, 'config', 'user.name', 't')
    (tmp_path / 'app.py').write_text('print("base")\n')
    _git(tmp_path, 'add', '.')
    _git(tmp_path, 'commit', '-qm', 'base')
    base = _git(tmp_path, 'rev-parse', 'HEAD')
    (tmp_path / 'app.py').write_text('print("base")\nimport os\nos.system(input())\n')
    # An attacker-authored attribute naming a textconv driver must not run.
    (tmp_path / '.gitattributes').write_text('*.py diff=evil\n')
    _git(tmp_path, 'add', '.')
    _git(tmp_path, 'commit', '-qm', 'head')
    head = _git(tmp_path, 'rev-parse', 'HEAD')
    return tmp_path, base, head


def _responses(base, head):
    def get(url, headers=None):
        r = Mock()
        if headers and headers.get('Accept') == 'application/vnd.github.diff':
            r.status_code = 406
            r.raise_for_status.side_effect = AssertionError('406 must not raise')
            return r
        r.status_code = 200
        r.raise_for_status = Mock()
        if '/compare/' in url:
            r.json.return_value = {'merge_base_commit': {'sha': base}}
        else:
            r.json.return_value = {'base': {'sha': base}, 'head': {'sha': head}}
        return r
    return get


def test_406_builds_the_diff_from_git(repo):
    path, base, head = repo
    with patch.dict(os.environ, {'GITHUB_TOKEN': 't', 'REPO_PATH': str(path)}), \
         patch('requests.get', side_effect=_responses(base, head)):
        diff = GitHubActionClient().get_pr_diff('o/r', 1)
    assert 'diff --git a/app.py b/app.py' in diff
    assert '+os.system(input())' in diff


def test_406_refuses_when_the_checkout_is_not_the_head(repo):
    path, base, head = repo
    _git(path, 'checkout', '-q', base)
    with patch.dict(os.environ, {'GITHUB_TOKEN': 't', 'REPO_PATH': str(path)}), \
         patch('requests.get', side_effect=_responses(base, head)):
        with pytest.raises(AuditError, match='not the pull request head'):
            GitHubActionClient().get_pr_diff('o/r', 1)


def test_406_does_not_run_a_textconv_driver(repo, tmp_path_factory):
    path, base, head = repo
    marker = tmp_path_factory.mktemp('m') / 'ran'
    _git(path, 'config', 'diff.evil.textconv', f'sh -c "touch {marker}; cat" --')
    with patch.dict(os.environ, {'GITHUB_TOKEN': 't', 'REPO_PATH': str(path)}), \
         patch('requests.get', side_effect=_responses(base, head)):
        GitHubActionClient().get_pr_diff('o/r', 1)
    assert not marker.exists()
