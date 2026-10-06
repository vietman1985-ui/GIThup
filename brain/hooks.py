"""Claude Code hook handlers.

Each handler reads the hook payload (JSON on stdin), does its work, and
prints either nothing or a JSON object with ``hookSpecificOutput.additionalContext``
so the text is injected into Claude's context.  Handlers never raise: a
broken brain must not break the user's session, so every failure degrades to
"print nothing, exit 0" (diagnostics go to stderr when BRAIN_DEBUG=1).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any, Dict, Optional, Tuple

from .config import Config
from .context import build_context, format_recall
from .index import Index
from .memory import session_end, session_prompt, session_start, session_touch

EVENTS = ("session-start", "prompt", "post-tool", "session-end", "stop", "pre-compact")

# Claude Code event names, used in hookSpecificOutput.hookEventName
EVENT_NAMES = {
    "session-start": "SessionStart",
    "prompt": "UserPromptSubmit",
    "post-tool": "PostToolUse",
    "session-end": "SessionEnd",
    "stop": "Stop",
    "pre-compact": "PreCompact",
}


def _debug(msg: str) -> None:
    if os.environ.get("BRAIN_DEBUG"):
        sys.stderr.write(f"[brain hook] {msg}\n")


def _context_output(event: str, text: str) -> str:
    if not text.strip():
        return ""
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": EVENT_NAMES[event], "additionalContext": text}},
        ensure_ascii=False,
    )


def handle(config: Config, event: str, payload: Dict[str, Any]) -> Tuple[str, int]:
    """Return ``(stdout_text, exit_code)``."""
    session_id = str(payload.get("session_id") or "unknown")
    cwd = str(payload.get("cwd") or os.getcwd())

    if event == "session-start":
        source = str(payload.get("source") or "startup")
        _, inject = session_start(config, session_id, cwd, source=source)
        if not inject:
            return "", 0
        with Index(config) as index:
            text = build_context(config, index, cwd=cwd)
        return _context_output(event, text), 0

    if event == "prompt":
        prompt = str(payload.get("prompt") or "")
        fresh = session_prompt(config, session_id, prompt)
        if not fresh or not config.get("auto_recall", True):
            return "", 0
        stripped = prompt.strip()
        if len(stripped) < 8 or stripped.startswith("/"):
            return "", 0
        k = int(config.get("recall_k", 3))
        min_score = float(config.get("recall_min_score", 1.0))
        with Index(config) as index:
            index.refresh()
            hits = [h for h in index.search(stripped, k=k, types=["fact", "entity", "decision", "preference", "procedure", "wiki"]) if h.score >= min_score]
        return _context_output(event, format_recall(hits)), 0

    if event == "post-tool":
        tool_input = payload.get("tool_input") or {}
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
        if isinstance(path, str) and path:
            session_touch(config, session_id, path)
        return "", 0

    if event == "session-end":
        session_end(config, session_id, reason=str(payload.get("reason") or ""))
        return "", 0

    if event in ("stop", "pre-compact"):
        return "", 0

    return "", 0


def run(config: Config, event: str, stdin_text: Optional[str] = None) -> int:
    if event not in EVENTS:
        sys.stderr.write(f"unknown hook event {event!r}; expected one of {', '.join(EVENTS)}\n")
        return 2
    raw = stdin_text if stdin_text is not None else sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    try:
        out, code = handle(config, event, payload)
    except Exception as exc:  # never break the user's session
        _debug(f"{event} failed: {exc}\n{traceback.format_exc()}")
        return 0
    if out:
        sys.stdout.write(out + "\n")
        sys.stdout.flush()
    return code
