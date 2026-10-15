"""The per-attempt scan limit can be set by the caller (superseedvc/superseed-internal#10763)."""
import importlib
import os

from claudecode import constants


def _reload_with(value):
    old = os.environ.pop('CLAUDECODE_TIMEOUT_MINUTES', None)
    try:
        if value is not None:
            os.environ['CLAUDECODE_TIMEOUT_MINUTES'] = value
        return importlib.reload(constants).SUBPROCESS_TIMEOUT
    finally:
        os.environ.pop('CLAUDECODE_TIMEOUT_MINUTES', None)
        if old is not None:
            os.environ['CLAUDECODE_TIMEOUT_MINUTES'] = old
        importlib.reload(constants)


def test_unset_keeps_twenty_minutes():
    assert _reload_with(None) == 1200


def test_caller_sets_forty_five_minutes():
    assert _reload_with('45') == 2700


def test_invalid_values_keep_twenty_minutes():
    for bad in ('', '0', '121', '-5', '4.5', 'forty'):
        assert _reload_with(bad) == 1200, bad
