"""
Constants and configuration values for ClaudeCode.
"""

import os

# API Configuration
# SuperSeed fork: no model id is compiled in. The caller names the model through the
# environment, from its own read of the SuperSeed model broker (GET /broker/assignments).
# An unset or empty variable leaves the value empty, and main() refuses to run on it.
DEFAULT_CLAUDE_MODEL = (os.environ.get('CLAUDE_MODEL') or '').strip()
# The findings filter's model. It defaults to the scan's model; the caller may set it apart.
FILTER_CLAUDE_MODEL = (os.environ.get('CLAUDE_FILTER_MODEL') or '').strip() or DEFAULT_CLAUDE_MODEL
DEFAULT_TIMEOUT_SECONDS = 180  # 3 minutes
DEFAULT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_MAX = 30  # Maximum backoff time for rate limits

# Token Limits
PROMPT_TOKEN_LIMIT = 16384  # 16k tokens max for claude-opus-4

# Exit Codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2

# Subprocess Configuration
def _subprocess_timeout_seconds():
    """The per-attempt limit on one Claude Code run, in seconds.

    SuperSeed fork (superseedvc/superseed-internal#10763): the caller may set
    CLAUDECODE_TIMEOUT_MINUTES, a whole number from 1 to 120. Anything else, or
    nothing, keeps the upstream 20 minutes. A dependency bump timed out at 20
    minutes three times running on 15 Oct 2026, with no finding.
    """
    raw = (os.environ.get('CLAUDECODE_TIMEOUT_MINUTES') or '').strip()
    if raw.isdigit() and 1 <= int(raw) <= 120:
        return int(raw) * 60
    return 1200


SUBPROCESS_TIMEOUT = _subprocess_timeout_seconds()  # 20 minutes unless the caller sets it

