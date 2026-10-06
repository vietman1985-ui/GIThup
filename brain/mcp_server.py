"""Minimal MCP (Model Context Protocol) server over stdio — standard library only.

Speaks JSON-RPC 2.0, newline-delimited (also tolerates Content-Length
framing).  Exposes the brain as tools so Claude Code, Claude Desktop, Cursor
or any MCP client can search, read and write the vault.

Run with ``brain mcp``; register with ``claude mcp add brain -- brain mcp``
or via the repo's ``.mcp.json``.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

from . import __version__
from .config import Config
from .context import build_context, format_hits
from .index import Index
from .lint import format_issues, run_lint
from .memory import (
    capture,
    consolidation_packet,
    log_event,
    remember,
    resolve,
    set_status,
)
from .notes import load_note

SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

INSTRUCTIONS = (
    "This is the user's second brain: a Markdown vault with episodic logs, semantic memory "
    "(facts, entities, decisions, preferences), procedures and a compiled wiki. "
    "Call brain_search before answering questions about the user, their projects or past decisions; "
    "call brain_read to get a full note; call brain_remember to store durable facts (ADD/UPDATE/SUPERSEDE); "
    "call brain_capture for quick, unprocessed notes; call brain_log to append to today's episodic log."
)


def _text(text: str, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class BrainServer:
    def __init__(self, config: Config):
        self.config = config
        self.index = Index(config)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, Callable[[Dict[str, Any]], str]] = {}
        self._register_tools()

    # ----------------------------------------------------------------- tools
    def _tool(self, name: str, description: str, properties: Dict[str, Any], required: Optional[List[str]] = None):
        def deco(fn: Callable[[Dict[str, Any]], str]):
            self.tools[name] = {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required or [],
                    "additionalProperties": False,
                },
            }
            self.handlers[name] = fn
            return fn

        return deco

    def _register_tools(self) -> None:
        @self._tool(
            "brain_search",
            "Full-text search over the brain (BM25 ranked, boosted by importance and recency). "
            "Returns matching notes with paths, metadata and snippets.",
            {
                "query": {"type": "string", "description": "Free-text query (Vietnamese or English)."},
                "k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8},
                "types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["fact", "entity", "decision", "preference", "procedure", "wiki", "raw", "episode", "inbox", "moc"]},
                    "description": "Restrict to note types.",
                },
                "tag": {"type": "string", "description": "Only notes carrying this tag."},
                "include_archived": {"type": "boolean", "default": False},
            },
            ["query"],
        )
        def _search(a: Dict[str, Any]) -> str:
            self.index.refresh()
            hits = self.index.search(
                a["query"], k=int(a.get("k") or 8), types=a.get("types"), tag=a.get("tag"), include_archived=bool(a.get("include_archived"))
            )
            return format_hits(hits)

        @self._tool(
            "brain_read",
            "Read one note in full (frontmatter + body), plus its backlinks and related notes.",
            {"path": {"type": "string", "description": "Vault-relative path, [[wikilink]] or note title/stem."}},
            ["path"],
        )
        def _read(a: Dict[str, Any]) -> str:
            self.index.refresh()
            path = resolve(self.config, self.index, a["path"])
            if path is None:
                raise FileNotFoundError(f"note not found: {a['path']}")
            note = load_note(self.config.vault, path)
            text = path.read_text(encoding="utf-8")
            extra = []
            back = self.index.backlinks(note.rel)
            if back:
                extra.append("Backlinks: " + ", ".join(back))
            rel = self.index.related(note.rel, k=6)
            if rel:
                extra.append("Related: " + ", ".join(f"{r} ({why})" for r, why, _ in rel))
            return f"<!-- {note.rel} -->\n{text}" + ("\n\n" + "\n".join(extra) if extra else "")

        @self._tool(
            "brain_remember",
            "Store durable knowledge as a semantic note. Decide the action first: ADD (new), UPDATE (same subject, "
            "more detail; appends an Update section), SUPERSEDE (contradicts an old note; pass supersedes), "
            "or do nothing (NOOP). Returns the path, the action taken and near-duplicate candidates.",
            {
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Markdown body. One idea per note. Cite sources with [[wikilinks]] or URLs."},
                "type": {"type": "string", "enum": ["fact", "entity", "decision", "preference", "procedure", "wiki"], "default": "fact"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "importance": {"type": "integer", "minimum": 0, "maximum": 10, "default": 5, "description": "10 = core identity/preferences; 5 = normal; 1 = trivia."},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.8},
                "sources": {"type": "array", "items": {"type": "string"}},
                "supersedes": {"type": "string", "description": "Path/stem of the note this one replaces (marks it superseded)."},
                "if_exists": {"type": "string", "enum": ["update", "new", "skip"], "default": "update"},
            },
            ["title", "content"],
        )
        def _remember(a: Dict[str, Any]) -> str:
            path, action, near = remember(
                self.config,
                self.index,
                title=a["title"],
                content=a["content"],
                type_=a.get("type") or "fact",
                tags=a.get("tags") or [],
                importance=int(a.get("importance") if a.get("importance") is not None else 5),
                confidence=float(a.get("confidence") if a.get("confidence") is not None else 0.8),
                sources=a.get("sources") or [],
                supersedes=a.get("supersedes"),
                if_exists=a.get("if_exists") or "update",
            )
            rel = path.relative_to(self.config.vault).as_posix()
            out = [f"{action}: {rel}"]
            near = [(r, s) for r, s in near if r != rel]
            if near:
                out.append("Similar existing notes (consider UPDATE/SUPERSEDE instead of a new note): " + ", ".join(f"{r} (score {s})" for r, s in near))
            return "\n".join(out)

        @self._tool(
            "brain_capture",
            "Quick capture into inbox/ without deciding where it belongs. Processed later by /brain:review.",
            {"text": {"type": "string"}, "title": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
            ["text"],
        )
        def _capture(a: Dict[str, Any]) -> str:
            path = capture(self.config, a["text"], title=a.get("title"), tags=a.get("tags") or [], source="mcp")
            return f"captured: {path.relative_to(self.config.vault).as_posix()}"

        @self._tool(
            "brain_log",
            "Append one line to today's episodic log (what happened / what was decided). Use kind='remember' to flag a candidate fact for consolidation.",
            {"text": {"type": "string"}, "kind": {"type": "string", "default": "note", "description": "note | remember | decision | session | todo"}},
            ["text"],
        )
        def _log(a: Dict[str, Any]) -> str:
            path = log_event(self.config, a["text"], kind=a.get("kind") or "note")
            return f"logged to {path.relative_to(self.config.vault).as_posix()}"

        @self._tool(
            "brain_related",
            "Notes connected to a given note through wikilinks (both directions) or shared tags.",
            {"path": {"type": "string"}, "k": {"type": "integer", "default": 8}},
            ["path"],
        )
        def _related(a: Dict[str, Any]) -> str:
            self.index.refresh()
            path = resolve(self.config, self.index, a["path"])
            if path is None:
                raise FileNotFoundError(f"note not found: {a['path']}")
            rel = path.relative_to(self.config.vault).as_posix()
            rows = self.index.related(rel, k=int(a.get("k") or 8))
            return "\n".join(f"- {r} — {why} (weight {w:g})" for r, why, w in rows) or "(no related notes)"

        @self._tool(
            "brain_context",
            "The session-start context packet: project notes, core memory, recent activity — trimmed to a budget.",
            {"cwd": {"type": "string"}, "budget": {"type": "integer", "default": 2400}},
        )
        def _context(a: Dict[str, Any]) -> str:
            return build_context(self.config, self.index, cwd=a.get("cwd") or "", budget=int(a.get("budget") or 0))

        @self._tool("brain_lint", "Vault health report: broken links, orphans, duplicates, stale or low-confidence notes, inbox backlog.", {})
        def _lint(a: Dict[str, Any]) -> str:
            self.index.refresh()
            return format_issues(run_lint(self.config, self.index))

        @self._tool(
            "brain_packet",
            "Consolidation packet for the weekly review: recent episodes, inbox, candidate facts, duplicates, stale notes, and the ADD/UPDATE/SUPERSEDE/NOOP decision table.",
            {"days": {"type": "integer", "default": 7}},
        )
        def _packet(a: Dict[str, Any]) -> str:
            return consolidation_packet(self.config, self.index, days=int(a.get("days") or 7))

        @self._tool(
            "brain_set_status",
            "Change a note's status: active | superseded | archived | draft.",
            {"path": {"type": "string"}, "status": {"type": "string", "enum": ["active", "superseded", "archived", "draft"]}},
            ["path", "status"],
        )
        def _set_status(a: Dict[str, Any]) -> str:
            path = set_status(self.config, self.index, a["path"], a["status"])
            return f"{path.relative_to(self.config.vault).as_posix()} → {a['status']}"

        @self._tool(
            "brain_list",
            "List notes by type/status, most important first.",
            {
                "types": {"type": "array", "items": {"type": "string"}},
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
        )
        def _list(a: Dict[str, Any]) -> str:
            self.index.refresh()
            rows = self.index.notes(types=a.get("types"), status=a.get("status"), limit=int(a.get("limit") or 30))
            return "\n".join(f"- [{r['type']}] {r['title']} ({r['rel']}) imp {r['importance']} · {r['status']} · {r['updated'] or '?'}" for r in rows) or "(none)"

        @self._tool("brain_stats", "Counts of notes, links and tags in the vault.", {})
        def _stats(a: Dict[str, Any]) -> str:
            self.index.refresh()
            return json.dumps(self.index.stats(), ensure_ascii=False, indent=2)

    # --------------------------------------------------------------- protocol
    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        is_notification = "id" not in msg

        if method == "initialize":
            requested = str(params.get("protocolVersion") or SUPPORTED_PROTOCOLS[0])
            version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            return self._ok(msg_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "brain", "version": __version__},
                "instructions": INSTRUCTIONS,
            })
        if method in ("notifications/initialized", "notifications/cancelled", "notifications/roots/list_changed"):
            return None
        if is_notification:
            return None
        if method == "ping":
            return self._ok(msg_id, {})
        if method == "tools/list":
            return self._ok(msg_id, {"tools": list(self.tools.values())})
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = self.handlers.get(name)
            if handler is None:
                return self._err(msg_id, -32602, f"unknown tool: {name}")
            try:
                return self._ok(msg_id, _text(handler(args)))
            except Exception as exc:  # tool errors are results, not protocol errors
                return self._ok(msg_id, _text(f"{type(exc).__name__}: {exc}", is_error=True))
        if method in ("resources/list", "resources/templates/list"):
            return self._ok(msg_id, {"resources": [], "resourceTemplates": []} if method.endswith("templates/list") else {"resources": []})
        if method == "prompts/list":
            return self._ok(msg_id, {"prompts": []})
        return self._err(msg_id, -32601, f"method not found: {method}")

    @staticmethod
    def _ok(msg_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _err(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _read_message(stream) -> Optional[str]:
    """Read one JSON-RPC message: a JSON line, or a Content-Length framed body."""
    while True:
        line = stream.readline()
        if not line:
            return None
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("content-length:"):
            length = int(stripped.split(":", 1)[1].strip())
            # consume remaining headers
            while True:
                hdr = stream.readline()
                if not hdr or not hdr.strip():
                    break
            body = stream.read(length)
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            return body
        return stripped


def serve(config: Config) -> int:
    server = BrainServer(config)
    stdin = sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin
    out = sys.stdout
    while True:
        raw = _read_message(stdin)
        if raw is None:
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            out.write(json.dumps(resp) + "\n")
            out.flush()
            continue
        messages = msg if isinstance(msg, list) else [msg]
        for m in messages:
            if not isinstance(m, dict):
                continue
            try:
                resp = server.handle(m)
            except Exception as exc:  # never die on a bad request
                sys.stderr.write("brain mcp error: %s\n%s" % (exc, traceback.format_exc()))
                resp = server._err(m.get("id"), -32603, f"internal error: {exc}")
            if resp is not None:
                out.write(json.dumps(resp, ensure_ascii=False) + "\n")
                out.flush()
    server.index.close()
    return 0
