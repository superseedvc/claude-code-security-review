"""Security audit prompt templates."""

import json
import re

# SuperSeed fork (superseedvc/superseed-internal#10267): the caller may name a JSON file holding
# the prompt variant its bank measured for the model it assigns. The file is
# {"variant": name, "system": text, "user": text}; the user text carries the tokens below and
# must carry {{PR_DIFF}}. Without the variable the scanner's own prompt is sent, unchanged.
PROMPT_TEMPLATE_ENV = 'SECURITY_SCAN_PROMPT_TEMPLATE'

_TOKEN = re.compile(r"\{\{(PR_[A-Z_]+)\}\}")

DIFF_OMITTED = (
    "(The diff was omitted because of its size. Use the file exploration tools to read the "
    "files listed above, which this pull request changes.)"
)


def load_prompt_template(path):
    """Read and check the caller's rendered prompt variant. Raises ValueError on any defect."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the prompt template is not a JSON object")
    for key in ('variant', 'system', 'user'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"{path}: the prompt template has no {key!r} text")
    if '{{PR_DIFF}}' not in data['user']:
        raise ValueError(f"{path}: the prompt template's user text has no {{{{PR_DIFF}}}} slot")
    return data


def render_prompt_template(template, pr_data, pr_diff=None, include_diff=True):
    """Fill in the pull request, in ONE pass, so a token inside the pull request's own text
    (its title, a file name, the diff) is never substituted again. Returns (system, user)."""
    values = {
        'PR_NUMBER': str(pr_data['number']),
        'PR_TITLE': str(pr_data['title']),
        'PR_AUTHOR': str(pr_data['user']),
        'PR_REPO': pr_data.get('head', {}).get('repo', {}).get('full_name', 'unknown'),
        'PR_CHANGED_FILES': str(pr_data['changed_files']),
        'PR_ADDITIONS': str(pr_data['additions']),
        'PR_DELETIONS': str(pr_data['deletions']),
        # The template writes "- {{PR_FILES}}", so the list continues the first bullet.
        'PR_FILES': "\n- ".join(f['filename'] for f in pr_data['files']),
        'PR_DIFF': (pr_diff or '') if include_diff else DIFF_OMITTED,
    }
    fill = lambda m: values.get(m.group(1), m.group(0))
    return _TOKEN.sub(fill, template['system']), _TOKEN.sub(fill, template['user'])


def get_security_audit_prompt(pr_data, pr_diff=None, include_diff=True, custom_scan_instructions=None):
    """Generate security audit prompt for Claude Code.
    
    Args:
        pr_data: PR data dictionary from GitHub API
        pr_diff: Optional complete PR diff in unified format
        include_diff: Whether to include the diff in the prompt (default: True)
        custom_scan_instructions: Optional custom security categories to append
        
    Returns:
        Formatted prompt string
    """
    
    files_changed = "\n".join([f"- {f['filename']}" for f in pr_data['files']])
    
    # Add diff section if provided and include_diff is True
    diff_section = ""
    if pr_diff and include_diff:
        diff_section = f"""

PR DIFF CONTENT:
```
{pr_diff}
```

Review the complete diff above. This contains all code changes in the PR.
"""
    elif pr_diff and not include_diff:
        diff_section = """

NOTE: PR diff was omitted due to size constraints. Please use the file exploration tools to examine the specific files that were changed in this PR.
"""
    
    # Add custom security categories if provided
    custom_categories_section = ""
    if custom_scan_instructions:
        custom_categories_section = f"\n{custom_scan_instructions}\n"
    
    return f"""
You are a senior security engineer conducting a focused security review of GitHub PR #{pr_data['number']}: "{pr_data['title']}"

CONTEXT:
- Repository: {pr_data.get('head', {}).get('repo', {}).get('full_name', 'unknown')}
- Author: {pr_data['user']}
- Files changed: {pr_data['changed_files']}
- Lines added: {pr_data['additions']}
- Lines deleted: {pr_data['deletions']}

Files modified:
{files_changed}{diff_section}

OBJECTIVE:
Perform a security-focused code review to identify HIGH-CONFIDENCE security vulnerabilities that could have real exploitation potential. This is not a general code review - focus ONLY on security implications newly added by this PR. Do not comment on existing security concerns.

CRITICAL INSTRUCTIONS:
1. MINIMIZE FALSE POSITIVES: Only flag issues where you're >80% confident of actual exploitability
2. AVOID NOISE: Skip theoretical issues, style concerns, or low-impact findings
3. FOCUS ON IMPACT: Prioritize vulnerabilities that could lead to unauthorized access, data breaches, or system compromise
4. EXCLUSIONS: Do NOT report the following issue types:
   - Denial of Service (DOS) vulnerabilities, even if they allow service disruption
   - Secrets or sensitive data stored on disk (these are handled by other processes)
   - Rate limiting or resource exhaustion issues

SECURITY CATEGORIES TO EXAMINE:

**Input Validation Vulnerabilities:**
- SQL injection via unsanitized user input
- Command injection in system calls or subprocesses
- XXE injection in XML parsing
- Template injection in templating engines
- NoSQL injection in database queries
- Path traversal in file operations

**Authentication & Authorization Issues:**
- Authentication bypass logic
- Privilege escalation paths
- Session management flaws
- JWT token vulnerabilities
- Authorization logic bypasses

**Crypto & Secrets Management:**
- Hardcoded API keys, passwords, or tokens
- Weak cryptographic algorithms or implementations
- Improper key storage or management
- Cryptographic randomness issues
- Certificate validation bypasses

**Injection & Code Execution:**
- Remote code execution via deseralization
- Pickle injection in Python
- YAML deserialization vulnerabilities
- Eval injection in dynamic code execution
- XSS vulnerabilities in web applications (reflected, stored, DOM-based)

**Data Exposure:**
- Sensitive data logging or storage
- PII handling violations
- API endpoint data leakage
- Debug information exposure
{custom_categories_section}
Additional notes:
- Even if something is only exploitable from the local network, it can still be a HIGH severity issue

ANALYSIS METHODOLOGY:

Phase 1 - Repository Context Research (Use file search tools):
- Identify existing security frameworks and libraries in use
- Look for established secure coding patterns in the codebase
- Examine existing sanitization and validation patterns
- Understand the project's security model and threat model

Phase 2 - Comparative Analysis:
- Compare new code changes against existing security patterns
- Identify deviations from established secure practices
- Look for inconsistent security implementations
- Flag code that introduces new attack surfaces

Phase 3 - Vulnerability Assessment:
- Examine each modified file for security implications
- Trace data flow from user inputs to sensitive operations
- Look for privilege boundaries being crossed unsafely
- Identify injection points and unsafe deserialization

REQUIRED OUTPUT FORMAT:

You MUST output your findings as structured JSON with this exact schema:

{{
  "findings": [
    {{
      "file": "path/to/file.py",
      "line": 42,
      "severity": "HIGH",
      "category": "sql_injection",
      "description": "User input passed to SQL query without parameterization",
      "exploit_scenario": "Attacker could extract database contents by manipulating the 'search' parameter with SQL injection payloads like '1; DROP TABLE users--'",
      "recommendation": "Replace string formatting with parameterized queries using SQLAlchemy or equivalent",
      "confidence": 0.95
    }}
  ],
  "analysis_summary": {{
    "files_reviewed": 8,
    "high_severity": 1,
    "medium_severity": 0,
    "low_severity": 0,
    "review_completed": true,
  }}
}}

SEVERITY GUIDELINES:
- **HIGH**: Directly exploitable vulnerabilities leading to RCE, data breach, or authentication bypass
- **MEDIUM**: Vulnerabilities requiring specific conditions but with significant impact
- **LOW**: Defense-in-depth issues or lower-impact vulnerabilities

CONFIDENCE SCORING:
- 0.9-1.0: Certain exploit path identified, tested if possible
- 0.8-0.9: Clear vulnerability pattern with known exploitation methods  
- 0.7-0.8: Suspicious pattern requiring specific conditions to exploit
- Below 0.7: Don't report (too speculative)

FINAL REMINDER:
Focus on HIGH and MEDIUM findings only. Better to miss some theoretical issues than flood the report with false positives. Each finding should be something a security engineer would confidently raise in a PR review.

IMPORTANT EXCLUSIONS - DO NOT REPORT:
- Denial of Service (DOS) vulnerabilities or resource exhaustion attacks
- Secrets/credentials stored on disk (these are managed separately)
- Rate limiting concerns or service overload scenarios. Services do not need to implement rate limiting.
- Memory consumption or CPU exhaustion issues.
- Lack of input validation on non-security-critical fields. If there isn't a proven problem from a lack of input validation, don't report it.

Begin your analysis now. Use the repository exploration tools to understand the codebase context, then analyze the PR changes for security implications.

Your final reply must contain the JSON and nothing else. You should not reply again after outputting the JSON.
"""