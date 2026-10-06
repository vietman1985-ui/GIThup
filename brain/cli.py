"""``brain`` command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import Config, load_config
from .context import build_context, format_hits, format_recall
from .index import Index
from .lint import format_issues, run_lint
from .memory import (
    capture,
    consolidation_packet,
    ensure_vault,
    init_vault,
    log_event,
    remember,
    resolve,
    set_status,
)
from .notes import load_note

REPO_ROOT = Path(__file__).resolve().parent.parent


def _split_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]


def _read_content(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    if getattr(args, "stdin", False) or (getattr(args, "content", None) in (None, "-") and not sys.stdin.isatty()):
        data = sys.stdin.read()
        if data.strip():
            return data
    return getattr(args, "content", None) or ""


def _require_vault(config: Config) -> None:
    if not config.vault.is_dir():
        sys.stderr.write(
            f"vault not found at {config.vault} (resolved from {config.source}).\n"
            "Run `brain init` to create it, set BRAIN_VAULT, or add a .brain.toml.\n"
        )
        raise SystemExit(3)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="A plain-Markdown second brain for Claude (and any MCP client).")
    p.add_argument("--vault", help="Vault directory (overrides BRAIN_VAULT and .brain.toml).")
    p.add_argument("--version", action="version", version=f"brain {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="Create the vault skeleton (and seed it from the repo's example vault).")
    s.add_argument("--template", help="Directory to copy as the initial vault (default: the repo's vault/ if present).")
    s.add_argument("--no-template", action="store_true", help="Create an empty skeleton only.")
    s.add_argument("--force", action="store_true", help="Overwrite files that already exist.")

    sub.add_parser("where", help="Print the resolved vault path and where it came from.")
    sub.add_parser("doctor", help="Check Python, SQLite FTS5, vault, index and hook wiring.")

    s = sub.add_parser("index", help="(Re)build the search index incrementally.")
    s.add_argument("--full", action="store_true", help="Re-read every file.")

    for name, help_ in (("search", "Search notes."), ("recall", "Search and format as a context packet.")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("query", nargs="+")
        s.add_argument("-k", type=int, default=8)
        s.add_argument("--type", action="append", dest="types", help="Restrict to a note type (repeatable).")
        s.add_argument("--tag")
        s.add_argument("--all", action="store_true", help="Include archived notes.")
        s.add_argument("--json", action="store_true")

    s = sub.add_parser("read", help="Print a note (by path, [[wikilink]] or title).")
    s.add_argument("ref")
    s.add_argument("--meta", action="store_true", help="Also print backlinks and related notes.")

    s = sub.add_parser("related", help="Notes connected by links or shared tags.")
    s.add_argument("ref")
    s.add_argument("-k", type=int, default=8)

    s = sub.add_parser("remember", help="Store a semantic note (ADD / UPDATE / SUPERSEDE).")
    s.add_argument("title")
    s.add_argument("content", nargs="?", help="Markdown body; use '-' or --stdin to read stdin.")
    s.add_argument("--stdin", action="store_true")
    s.add_argument("--file")
    s.add_argument("--type", default="fact", choices=["fact", "entity", "decision", "preference", "procedure", "wiki"])
    s.add_argument("--tags", help="Comma-separated.")
    s.add_argument("--importance", type=int, default=5)
    s.add_argument("--confidence", type=float, default=0.8)
    s.add_argument("--source", action="append", default=[], help="Source reference (repeatable).")
    s.add_argument("--supersedes", help="Note this one replaces.")
    s.add_argument("--if-exists", default="update", choices=["update", "new", "skip"])

    s = sub.add_parser("capture", help="Quick capture into inbox/.")
    s.add_argument("content", nargs="?", help="Text; use '-' or --stdin to read stdin.")
    s.add_argument("--stdin", action="store_true")
    s.add_argument("--file")
    s.add_argument("--title")
    s.add_argument("--tags")

    s = sub.add_parser("log", help="Append a line to today's episodic log.")
    s.add_argument("text", nargs="+")
    s.add_argument("--kind", default="note")

    s = sub.add_parser("context", help="Print the session-start context packet.")
    s.add_argument("--cwd", default=os.getcwd())
    s.add_argument("--budget", type=int, default=0)

    s = sub.add_parser("lint", help="Vault health report.")
    s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true", help="Exit 1 when errors are present.")

    s = sub.add_parser("stats", help="Vault statistics.")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("packet", help="Consolidation packet for the weekly review.")
    s.add_argument("--days", type=int, default=7)

    s = sub.add_parser("status", help="Set a note's status.")
    s.add_argument("ref")
    s.add_argument("value", choices=["active", "superseded", "archived", "draft"])

    s = sub.add_parser("archive", help="Shortcut for `status <ref> archived`.")
    s.add_argument("ref")

    s = sub.add_parser("list", help="List notes.")
    s.add_argument("--type", action="append", dest="types")
    s.add_argument("--status")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--json", action="store_true")

    sub.add_parser("mcp", help="Run the MCP server on stdio.")

    s = sub.add_parser("hook", help="Claude Code hook entry point (reads the hook JSON on stdin).")
    s.add_argument("event", choices=["session-start", "prompt", "post-tool", "session-end", "stop", "pre-compact"])

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(vault_override=args.vault)

    if args.cmd == "where":
        print(f"{config.vault}  (from {config.source})")
        return 0

    if args.cmd == "init":
        template: Optional[Path] = None
        if not args.no_template:
            template = Path(args.template).expanduser() if args.template else (REPO_ROOT / "vault")
            if template.resolve() == config.vault.resolve():
                template = None  # initialising the seed vault itself
        created = init_vault(config, template_dir=template, force=args.force)
        print(f"vault: {config.vault}")
        for c in created:
            print(f"  + {c}")
        if not created:
            print("  (already initialised)")
        with Index(config) as index:
            counts = index.refresh(full=True)
        print(f"indexed: {counts}")
        return 0

    if args.cmd == "doctor":
        return _doctor(config)

    if args.cmd == "hook":
        from .hooks import run as run_hook

        try:
            ensure_vault(config, template_dir=REPO_ROOT / "vault")
        except OSError:
            pass
        if not config.vault.is_dir():
            return 0  # no vault and not allowed to create one: stay silent, never break the session
        return run_hook(config, args.event)

    if args.cmd == "mcp":
        from .mcp_server import serve

        ensure_vault(config, template_dir=REPO_ROOT / "vault")
        _require_vault(config)
        return serve(config)

    _require_vault(config)

    with Index(config) as index:
        if args.cmd == "index":
            counts = index.refresh(full=args.full)
            print(json.dumps(counts))
            return 0

        if args.cmd in ("search", "recall"):
            index.refresh()
            query = " ".join(args.query)
            hits = index.search(query, k=args.k, types=args.types, tag=args.tag, include_archived=args.all)
            if args.json:
                print(json.dumps([h.__dict__ for h in hits], ensure_ascii=False, indent=2))
            elif args.cmd == "recall":
                print(format_recall(hits, budget=10_000) or "(no relevant notes)")
            else:
                print(format_hits(hits))
            return 0

        if args.cmd == "read":
            index.refresh()
            path = resolve(config, index, args.ref)
            if path is None:
                sys.stderr.write(f"note not found: {args.ref}\n")
                return 1
            sys.stdout.write(path.read_text(encoding="utf-8"))
            if args.meta:
                note = load_note(config.vault, path)
                back = index.backlinks(note.rel)
                rel = index.related(note.rel)
                print("\n---")
                print("backlinks: " + (", ".join(back) or "(none)"))
                print("related: " + (", ".join(f"{r} ({why})" for r, why, _ in rel) or "(none)"))
            return 0

        if args.cmd == "related":
            index.refresh()
            path = resolve(config, index, args.ref)
            if path is None:
                sys.stderr.write(f"note not found: {args.ref}\n")
                return 1
            rel = path.relative_to(config.vault).as_posix()
            for r, why, w in index.related(rel, k=args.k):
                print(f"{r}\t{why}\t{w:g}")
            return 0

        if args.cmd == "remember":
            content = _read_content(args)
            if not content.strip():
                sys.stderr.write("remember: content is empty (pass it as an argument, via --stdin or --file)\n")
                return 1
            path, action, near = remember(
                config,
                index,
                title=args.title,
                content=content,
                type_=args.type,
                tags=_split_list(args.tags),
                importance=args.importance,
                confidence=args.confidence,
                sources=args.source,
                supersedes=args.supersedes,
                if_exists=args.if_exists,
            )
            rel = path.relative_to(config.vault).as_posix()
            print(f"{action}: {rel}")
            near = [(r, s) for r, s in near if r != rel]
            if near:
                print("similar: " + ", ".join(f"{r} ({s})" for r, s in near))
            return 0

        if args.cmd == "capture":
            content = _read_content(args)
            if not content.strip():
                sys.stderr.write("capture: nothing to capture\n")
                return 1
            path = capture(config, content, title=args.title, tags=_split_list(args.tags), source="cli")
            print(f"captured: {path.relative_to(config.vault).as_posix()}")
            return 0

        if args.cmd == "log":
            path = log_event(config, " ".join(args.text), kind=args.kind)
            print(f"logged: {path.relative_to(config.vault).as_posix()}")
            return 0

        if args.cmd == "context":
            print(build_context(config, index, cwd=args.cwd, budget=args.budget))
            return 0

        if args.cmd == "lint":
            index.refresh()
            issues = run_lint(config, index)
            if args.json:
                print(json.dumps([i.as_dict() for i in issues], ensure_ascii=False, indent=2))
            else:
                print(format_issues(issues))
            if args.strict and any(i.level == "error" for i in issues):
                return 1
            return 0

        if args.cmd == "stats":
            index.refresh()
            stats = index.stats()
            if args.json:
                print(json.dumps(stats, ensure_ascii=False, indent=2))
            else:
                print(f"vault:  {stats['vault']}")
                print(f"notes:  {stats['notes']}  " + " ".join(f"{t}={n}" for t, n in stats["by_type"].items()))
                print(f"links:  {stats['links']} resolved, {stats['broken_links']} broken")
                print(f"tags:   {stats['tags']}")
            return 0

        if args.cmd == "packet":
            print(consolidation_packet(config, index, days=args.days))
            return 0

        if args.cmd in ("status", "archive"):
            value = "archived" if args.cmd == "archive" else args.value
            try:
                path = set_status(config, index, args.ref, value)
            except FileNotFoundError:
                sys.stderr.write(f"note not found: {args.ref}\n")
                return 1
            print(f"{path.relative_to(config.vault).as_posix()} → {value}")
            return 0

        if args.cmd == "list":
            index.refresh()
            rows = index.notes(types=args.types, status=args.status, limit=args.limit)
            if args.json:
                print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2, default=str))
            else:
                for r in rows:
                    print(f"[{r['type']}] {r['title']}  ({r['rel']})  imp {r['importance']} · {r['status']} · {r['updated'] or '?'}")
            return 0

    parser.print_help()
    return 2


def _doctor(config: Config) -> int:
    ok = True

    def line(status: bool, text: str) -> None:
        nonlocal ok
        ok = ok and status
        print(("✔ " if status else "✘ ") + text)

    line(sys.version_info >= (3, 8), f"python {sys.version.split()[0]} (need ≥ 3.8)")
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        line(True, f"sqlite {sqlite3.sqlite_version} with FTS5")
    except sqlite3.OperationalError as exc:
        line(False, f"sqlite FTS5 unavailable: {exc}")
    line(config.vault.is_dir(), f"vault {config.vault} (from {config.source})")
    if config.vault.is_dir():
        try:
            with Index(config) as index:
                counts = index.refresh()
                stats = index.stats()
            line(True, f"index {config.index_path}: {stats['notes']} notes, {stats['links']} links, {counts}")
        except Exception as exc:  # pragma: no cover - diagnostics only
            line(False, f"index failed: {exc}")
        line((config.vault / "Home.md").exists(), "Home.md present")
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    print(("✔ " if plugin_root else "· ") + f"CLAUDE_PLUGIN_ROOT={plugin_root or '(not running inside a plugin hook)'}")
    hooks_json = REPO_ROOT / "hooks" / "hooks.json"
    line(hooks_json.exists(), f"plugin hooks file {hooks_json}")
    print("all good" if ok else "problems found")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
