"""secret scanning and redaction. runs before any content reaches the gateway:
an api key in a config file must never become a prompt."""

import re

PATTERNS = [
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github_classic_token", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("gitlab_token", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}")),
    ("generic_assignment", re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.+/]{16,}['\"]?"
    )),
    ("bearer_in_url", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.+/=]{20,}")),
]


def scan(text: str) -> list[tuple[str, re.Match]]:
    hits = []
    for name, pattern in PATTERNS:
        for m in pattern.finditer(text):
            hits.append((name, m))
    return hits


def redact(text: str) -> tuple[str, bool]:
    """returns (clean_text, had_secrets). every match becomes a named placeholder
    so line numbers stay true for provenance."""
    had = False
    for name, pattern in PATTERNS:
        if pattern.search(text):
            had = True
            text = pattern.sub(f"[REDACTED:{name}]", text)
    return text, had
