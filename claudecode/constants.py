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
SUBPROCESS_TIMEOUT = 1200  # 20 minutes for Claude Code execution

