"""Input sanitization utilities.

Provides functions that strip dangerous content from user-supplied text
to prevent stored XSS, log injection, and HTML injection.
"""

from __future__ import annotations

import html
import re

# Matches most HTML tags (opening, closing, self-closing)
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>", re.DOTALL)

# Matches common script injection patterns
_SCRIPT_RE = re.compile(
    r"(javascript\s*:|on\w+\s*=|<\s*script)", re.IGNORECASE
)


def sanitize_text(value: str | None) -> str:
    """Return a safely escaped version of *value*.

    * HTML entities are escaped (``<`` → ``&lt;``).
    * Bare ``<tag>`` fragments are removed.
    * Common script-injection patterns are stripped.
    * Leading/trailing whitespace is trimmed.
    """
    if not value:
        return ""
    cleaned = html.escape(value, quote=True)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _SCRIPT_RE.sub("", cleaned)
    return cleaned.strip()


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe version of *name*.

    Strips path traversal characters, collapses dots, and limits length.
    """
    if not name:
        return "document"
    safe = re.sub(r"[^\w.\-() ]", "_", name)
    # Collapse consecutive dots to prevent traversal
    safe = re.sub(r"\.{2,}", "_", safe)
    safe = safe.lstrip(".")
    return safe[:255] or "document"
