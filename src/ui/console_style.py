"""
console_style.py — Console log coloring for Media Organizer, AV1 Encoder, AI Scanner.
Returns hex color for message type; base text is bright white.
"""

# Bright white base
BASE = "#e5e7eb"
# Error/failure
ERROR = "#ef4444"
# Warning
WARNING = "#f59e0b"
# Success, done, complete
SUCCESS = "#10b981"
# Action tags [MOVE], [COPY], [LINK], [DRY RUN]
ACTION = "#22c55e"
# Skip, duplicate, rejected
SKIP = "#94a3b8"
# Status: scanning, starting, found
INFO = "#3b82f6"
# Deleted, failed
FAIL = "#dc2626"


def log_color_for_message(msg: str) -> str:
    """Return hex color for a log message. Order matters: check specific before generic."""
    if not msg or not isinstance(msg, str):
        return BASE
    u = msg.upper()
    if u.startswith("ERROR:") or u.startswith("FAILED:") or "ERROR:" in u[:25]:
        return ERROR
    if u.startswith("WARNING:") or "WARNING:" in u[:25]:
        return WARNING
    if u.startswith("REJECTED:") or "DELETE ERROR" in u or "EXPORT FAILED" in u:
        return FAIL
    if (
        u.startswith("DONE:")
        or "COMPLETE" in u
        or "BATCH ORGANIZATION COMPLETE" in u
        or "BATCH SCAN COMPLETE" in u
        or "MODEL SETUP COMPLETE" in u
        or "OPENCV INSTALLED" in u
    ):
        return SUCCESS
    if u.startswith("[MOVE]") or u.startswith("[COPY]") or u.startswith("[LINK]") or "[DRY RUN]" in u or "[RENAME FIX]" in u:
        return ACTION
    if u.startswith("[SKIP]") or u.startswith("[DUPLICATE]") or u.startswith("SKIP ("):
        return SKIP
    if u.startswith("DELETED:"):
        return SUCCESS
    if u.startswith("ENCODING STOPPED"):
        return SKIP
    if (
        u.startswith("SCANNING")
        or u.startswith("STARTING")
        or u.startswith("FOUND ")
        or u.startswith("SCANNED:")
        or u.startswith("STARTING MODEL")
    ):
        return INFO
    if "MOVED " in u or "COPIED " in u or "EXPORTED TO" in u:
        return SUCCESS
    if u.startswith("BUILDING FILE") or "ORGANIZATION (" in u:
        return INFO
    return BASE
