"""Memory operations: capture, remember, episodic log, session state, consolidation packet.

Memory tiers (borrowed from MemGPT/Letta, mem0 and Generative Agents):

* **episodic**   – append-only daily logs ``memory/episodic/YYYY-MM-DD.md``
                   (what happened: sessions, prompts, files touched, notes).
* **semantic**   – atomic facts/entities/decisions/preferences under
                   ``memory/semantic/`` with importance + confidence + status.
* **procedural** – how-tos the brain has learned, under ``memory/procedural/``.
* **wiki**       – compiled knowledge pages built from ``raw/`` sources.

``remember`` implements the mem0-style decision table — ADD / UPDATE /
SUPERSEDE / NOOP — in the deterministic part; the judgement about *which*
to apply is made by the calling agent (or by the ``--if-exists`` flag).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import Config, VAULT_DIRS
from .index import Index
from .notes import (
    NOTE_TYPES,
    dump_frontmatter,
    load_note,
    now_hm,
    parse_frontmatter,
    render_note,
    slugify,
    today,
)

TYPE_DIRS = {
    "fact": "memory/semantic/facts",
    "entity": "memory/semantic/entities",
    "decision": "memory/semantic/decisions",
    "preference": "memory/semantic/preferences",
    "procedure": "memory/procedural",
    "wiki": "wiki",
    "inbox": "inbox",
    "raw": "raw",
    "moc": "",
}


# ----------------------------------------------------------------------- init
def init_vault(config: Config, template_dir: Optional[Path] = None, force: bool = False) -> List[str]:
    """Create the vault skeleton.  Copies ``template_dir`` (the repo's seed
    vault) when given, otherwise writes a minimal Home.md and templates."""
    created: List[str] = []
    vault = config.vault
    vault.mkdir(parents=True, exist_ok=True)
    for d in VAULT_DIRS:
        p = vault / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(d + "/")
    for sub in TYPE_DIRS.values():
        if sub:
            (vault / sub).mkdir(parents=True, exist_ok=True)

    if template_dir is not None and template_dir.is_dir():
        for src in sorted(template_dir.rglob("*")):
            rel = src.relative_to(template_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            dst = vault / rel
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                continue
            if dst.exists() and not force:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            created.append(rel.as_posix())
    home = vault / "Home.md"
    if not home.exists():
        home.write_text(_default_home(), encoding="utf-8")
        created.append("Home.md")
    gitignore = vault / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".brain/\n.obsidian/workspace*.json\n", encoding="utf-8")
        created.append(".gitignore")
    return created


def ensure_vault(config: Config, template_dir: Optional[Path] = None) -> bool:
    """Create the vault on first use when it is the user-level default.

    Hooks and the MCP server call this so a freshly installed plugin works
    without a manual ``brain init``.  Only the schema and templates are
    copied from ``template_dir`` — never the example notes.  Returns True if
    the vault was created.
    """
    if config.vault.is_dir():
        return False
    if not config.source.startswith("default"):
        return False  # an explicit BRAIN_VAULT / .brain.toml that is missing is the user's call
    init_vault(config, template_dir=None)
    _copy_schema_and_templates(config, template_dir)
    return True


def _copy_schema_and_templates(config: Config, template_dir: Optional[Path]) -> None:
    if template_dir is None or not template_dir.is_dir():
        return
    src = template_dir / "_schema.md"
    if src.is_file() and not (config.vault / "_schema.md").exists():
        (config.vault / "_schema.md").write_bytes(src.read_bytes())
    tdir = template_dir / "_templates"
    if tdir.is_dir():
        for src in sorted(tdir.glob("*.md")):
            dst = config.vault / "_templates" / src.name
            if not dst.exists():
                dst.write_bytes(src.read_bytes())


def _default_home() -> str:
    fm = {"type": "moc", "title": "Home", "created": today(), "updated": today(), "importance": 10, "tags": ["moc"]}
    body = (
        "# Home\n\n"
        "Map of content for this brain. Start here. Link your most important notes from this page "
        "so nothing stays an orphan; see [[_schema]] for the note format.\n\n"
        "## Memory\n"
        "- Semantic notes: `memory/semantic/facts/`, `entities/`, `decisions/`, `preferences/`\n"
        "- Episodic log: `memory/episodic/` (one file per day, written by hooks)\n"
        "- Procedures: `memory/procedural/`\n\n"
        "## Knowledge\n"
        "- Wiki pages compiled from sources: `wiki/`\n"
        "- Raw sources (never edited by hand): `raw/`\n\n"
        "## Inbox\n"
        "- Unprocessed captures: `inbox/` — process with /brain:review\n"
    )
    return render_note(fm, body)


# -------------------------------------------------------------------- helpers
def _unique_path(directory: Path, stem: str) -> Path:
    candidate = directory / f"{stem}.md"
    n = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{n}.md"
        n += 1
    return candidate


def _norm_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[,\n]+", value) if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def write_note(path: Path, frontmatter: Dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_note(frontmatter, body), encoding="utf-8")


def update_frontmatter(path: Path, **changes: Any) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    for key, value in changes.items():
        if value is None:
            fm.pop(key, None)
        else:
            fm[key] = value
    fm["updated"] = today()
    path.write_text(render_note(fm, body), encoding="utf-8")
    return fm


# -------------------------------------------------------------------- capture
def capture(config: Config, text: str, title: Optional[str] = None, tags: Sequence[str] = (), source: str = "") -> Path:
    """Quick capture into inbox/.  Zero friction: title is optional."""
    text = text.strip()
    if not title:
        first = text.splitlines()[0] if text else "capture"
        title = re.sub(r"^[#\-\*\s]+", "", first)[:60] or "capture"
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    path = _unique_path(config.vault / "inbox", f"{stamp} {slugify(title, 50)}")
    fm: Dict[str, Any] = {
        "type": "inbox",
        "title": title,
        "created": today(),
        "updated": today(),
        "tags": list(tags),
        "status": "draft",
    }
    if source:
        fm["source"] = source
    body = f"# {title}\n\n{text}\n"
    write_note(path, fm, body)
    return path


# ------------------------------------------------------------------- remember
def remember(
    config: Config,
    index: Index,
    title: str,
    content: str,
    type_: str = "fact",
    tags: Sequence[str] = (),
    importance: int = 5,
    confidence: float = 0.8,
    sources: Sequence[str] = (),
    supersedes: Optional[str] = None,
    if_exists: str = "update",
) -> Tuple[Path, str, List[Tuple[str, float]]]:
    """Store a semantic/procedural note.

    Returns ``(path, action, near_duplicates)`` where action is one of
    ADD / UPDATE / SUPERSEDE / NOOP and near_duplicates lists
    ``(rel, score)`` of existing notes that look similar (for the agent to
    decide whether a merge is needed).
    """
    if type_ not in NOTE_TYPES or type_ in ("inbox", "episode", "raw", "template"):
        raise ValueError(f"type must be one of fact/entity/decision/preference/procedure/wiki, got {type_!r}")
    directory = config.vault / TYPE_DIRS[type_]
    directory.mkdir(parents=True, exist_ok=True)
    stem = slugify(title)
    index.refresh()

    # near-duplicates: an existing note of the same type whose title overlaps
    # the new title, or that covers most of what we are about to store
    near = [
        (h.rel, h.score)
        for h in index.search(f"{title} {content[:200]}", k=5, types=[type_])
        if h.title_hits >= 2 or h.coverage >= 0.5
    ]
    existing_rels = index.find_by_stem(stem)
    existing = (config.vault / existing_rels[0]) if existing_rels else None

    fm: Dict[str, Any] = {
        "type": type_,
        "title": title,
        "tags": list(dict.fromkeys(t.lstrip("#") for t in tags if t)),
        "created": today(),
        "updated": today(),
        "importance": int(max(0, min(10, importance))),
        "confidence": float(max(0.0, min(1.0, confidence))),
        "status": "active",
    }
    src_list = [s for s in sources if s]
    if src_list:
        fm["sources"] = src_list

    if supersedes:
        old_rel = _resolve_rel(config, index, supersedes)
        if old_rel is None:
            raise FileNotFoundError(f"cannot find note to supersede: {supersedes}")
        new_path = _unique_path(directory, stem) if (existing and existing.resolve() == (config.vault / old_rel).resolve()) or not existing else existing
        body = f"# {title}\n\n{content.strip()}\n\nSupersedes [[{Path(old_rel).stem}]].\n"
        fm["supersedes"] = f"[[{Path(old_rel).stem}]]"
        write_note(new_path, fm, body)
        update_frontmatter(config.vault / old_rel, status="superseded", superseded_by=f"[[{new_path.stem}]]")
        index.refresh()
        return new_path, "SUPERSEDE", near

    if existing is not None and existing.exists():
        if if_exists == "skip":
            return existing, "NOOP", near
        if if_exists == "new":
            path = _unique_path(directory, stem)
            write_note(path, fm, f"# {title}\n\n{content.strip()}\n")
            index.refresh()
            return path, "ADD", near
        # UPDATE: keep history inside the note, bump metadata
        text = existing.read_text(encoding="utf-8")
        old_fm, old_body = parse_frontmatter(text)
        merged_tags = list(dict.fromkeys(_norm_list(old_fm.get("tags")) + fm["tags"]))
        old_fm.update(
            {
                "title": title,
                "tags": merged_tags,
                "updated": today(),
                "importance": max(int(old_fm.get("importance") or 0), fm["importance"]),
                "confidence": fm["confidence"],
                "status": "active",
            }
        )
        if src_list:
            old_fm["sources"] = list(dict.fromkeys(_norm_list(old_fm.get("sources")) + src_list))
        if "created" not in old_fm:
            old_fm["created"] = today()
        new_body = old_body.rstrip("\n") + f"\n\n## Update {today()} {now_hm()}\n\n{content.strip()}\n"
        existing.write_text(render_note(old_fm, new_body), encoding="utf-8")
        index.refresh()
        return existing, "UPDATE", near

    path = directory / f"{stem}.md"
    write_note(path, fm, f"# {title}\n\n{content.strip()}\n")
    index.refresh()
    return path, "ADD", near


def _inside_vault(config: Config, p: Path) -> Optional[str]:
    """Vault-relative POSIX path if ``p`` is a file inside the vault, else None.

    Refuses anything that escapes the vault (``../``, absolute paths, symlinks
    pointing outside) so MCP clients can only ever read and modify notes.
    """
    try:
        resolved = p.resolve()
        rel = resolved.relative_to(config.vault.resolve())
    except (OSError, ValueError):
        return None
    if not resolved.is_file() or any(part.startswith(".") for part in rel.parts):
        return None
    return rel.as_posix()


def _resolve_rel(config: Config, index: Index, ref: str) -> Optional[str]:
    ref = ref.strip().strip("[]").split("|", 1)[0].split("#", 1)[0].strip()
    if not ref:
        return None
    for candidate in (ref, ref + ".md"):
        rel = _inside_vault(config, config.vault / candidate)
        if rel:
            return rel
    rels = index.find_by_stem(Path(ref).stem)
    return rels[0] if rels else None


def resolve(config: Config, index: Index, ref: str) -> Optional[Path]:
    rel = _resolve_rel(config, index, ref)
    return (config.vault / rel) if rel else None


def set_status(config: Config, index: Index, ref: str, status: str) -> Path:
    path = resolve(config, index, ref)
    if path is None:
        raise FileNotFoundError(ref)
    update_frontmatter(path, status=status)
    index.refresh()
    return path


# --------------------------------------------------------------- episodic log
def episodic_path(config: Config, day: Optional[str] = None) -> Path:
    day = day or today()
    return config.vault / "memory" / "episodic" / f"{day}.md"


def log_event(config: Config, text: str, kind: str = "note", day: Optional[str] = None, when: Optional[str] = None) -> Path:
    """Append ``- HH:MM [kind] text`` to today's episodic log."""
    path = episodic_path(config, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = re.sub(r"\s+", " ", text.strip())
    if not path.exists():
        fm = {"type": "episode", "title": path.stem, "created": path.stem, "updated": path.stem, "importance": 3, "tags": ["episodic"]}
        path.write_text(render_note(fm, f"# {path.stem}\n\n"), encoding="utf-8")
    line = f"- {when or now_hm()} [{kind}] {text}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    # keep `updated` honest without rewriting the whole file every time
    if path.stem != today():
        update_frontmatter(path)
    return path


def recent_episodes(config: Config, days: int = 2, max_lines: int = 12) -> List[str]:
    lines: List[str] = []
    for i in range(days):
        day = (_dt.date.today() - _dt.timedelta(days=i)).isoformat()
        p = episodic_path(config, day)
        if not p.exists():
            continue
        _, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        entries = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("- ")]
        for e in reversed(entries):
            lines.append(f"{day} {e[2:]}")
            if len(lines) >= max_lines:
                return lines
    return lines


# -------------------------------------------------------------- session state
def _session_file(config: Config, session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return config.sessions_dir / f"{safe}.json"


def load_session(config: Config, session_id: str) -> Dict[str, Any]:
    p = _session_file(config, session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"id": session_id, "started": _dt.datetime.now().isoformat(timespec="seconds"), "cwd": "", "prompts": [], "touched": []}


def save_session(config: Config, state: Dict[str, Any]) -> None:
    config.sessions_dir.mkdir(parents=True, exist_ok=True)
    _session_file(config, state.get("id", "unknown")).write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def session_start(config: Config, session_id: str, cwd: str, source: str = "startup") -> Tuple[Dict[str, Any], bool]:
    """Record a session start.  Returns ``(state, inject_context)``.

    The same event can reach us twice (plugin hooks *and* project hooks when
    developing this repo with the plugin installed), so logging and context
    injection are deduplicated per session + source.  ``compact`` always
    re-injects: the model just lost its context.
    """
    state = load_session(config, session_id)
    state["cwd"] = cwd
    state["source"] = source
    seen = state.setdefault("context_sources", [])
    inject = source == "compact" or source not in seen
    if source not in seen:
        seen.append(source)
    logged = state.setdefault("logged_sources", [])
    if config.get("auto_log", True) and source in ("startup", "resume") and source not in logged:
        logged.append(source)
        log_event(config, f"session {session_id[:8]} {source} in {cwd}", kind="session")
    save_session(config, state)
    return state, inject


def session_prompt(config: Config, session_id: str, prompt: str) -> bool:
    """Record a prompt; returns False when it duplicates the last recorded one
    (a second hook firing for the same event), so callers can skip recall."""
    state = load_session(config, session_id)
    short = re.sub(r"\s+", " ", prompt.strip())[:140]
    if not short:
        return False
    digest = hashlib.sha1(prompt.strip().encode("utf-8")).hexdigest()
    if state.get("last_prompt") == digest:
        return False
    state["last_prompt"] = digest
    state.setdefault("prompts", []).append(short)
    state["prompts"] = state["prompts"][-50:]
    save_session(config, state)
    return True


def session_touch(config: Config, session_id: str, file_path: str) -> None:
    if not file_path:
        return
    state = load_session(config, session_id)
    touched = state.setdefault("touched", [])
    if file_path not in touched:
        touched.append(file_path)
        state["touched"] = touched[-200:]
        save_session(config, state)


def session_end(config: Config, session_id: str, reason: str = "") -> Optional[Path]:
    state = load_session(config, session_id)
    prompts = state.get("prompts") or []
    touched = state.get("touched") or []
    if not prompts and not touched:
        _session_file(config, session_id).unlink(missing_ok=True)
        return None
    cwd = state.get("cwd") or ""
    parts = [f"session {session_id[:8]} ended" + (f" ({reason})" if reason else "") + (f" in {cwd}" if cwd else "")]
    if prompts:
        topics = "; ".join(p[:60] for p in prompts[:4])
        parts.append(f"topics: {topics}" + (" …" if len(prompts) > 4 else ""))
    if touched:
        shown = ", ".join(_short_path(t, cwd) for t in touched[:8])
        parts.append(f"touched {len(touched)} file(s): {shown}" + (" …" if len(touched) > 8 else ""))
    path = log_event(config, " | ".join(parts), kind="session")
    _session_file(config, session_id).unlink(missing_ok=True)
    return path


def _short_path(p: str, cwd: str) -> str:
    if cwd and p.startswith(cwd.rstrip("/") + "/"):
        return p[len(cwd.rstrip("/")) + 1:]
    return p


# ------------------------------------------------------- consolidation packet
def consolidation_packet(config: Config, index: Index, days: int = 7, max_items: int = 40) -> str:
    """Markdown brief for the consolidator agent: what happened, what is
    waiting in the inbox, what looks stale or duplicated."""
    index.refresh()
    out: List[str] = [f"# Consolidation packet — {today()} (last {days} days)", ""]

    out.append("## Episodic entries")
    episodes = recent_episodes(config, days=days, max_lines=max_items)
    out.extend(f"- {e}" for e in episodes) if episodes else out.append("- (none)")
    out.append("")

    out.append("## Inbox items")
    inbox = index.notes(types=["inbox"], order="created DESC", limit=max_items)
    if inbox:
        for r in inbox:
            out.append(f"- [[{r['stem']}]] — {r['summary'] or '(empty)'}")
    else:
        out.append("- (empty)")
    out.append("")

    out.append("## Candidate facts mentioned in logs (lines tagged #remember)")
    cands = [e for e in episodes if "#remember" in e or "[remember]" in e]
    out.extend(f"- {c}" for c in cands) if cands else out.append("- (none)")
    out.append("")

    out.append("## Possible duplicates")
    dups = index.duplicate_titles()
    out.extend(f"- '{t}': {', '.join(rels)}" for t, rels in dups) if dups else out.append("- (none)")
    out.append("")

    stale_after = float(config.get("stale_after_days", 180))
    out.append(f"## Stale or low-confidence (active, >{int(stale_after)} days or confidence < 0.5)")
    flagged = []
    for r in index.notes(types=["fact", "entity", "decision", "preference", "procedure"], status="active"):
        try:
            age = (_dt.date.today() - _dt.date.fromisoformat(str(r["updated"] or r["created"])[:10])).days
        except (TypeError, ValueError):
            age = 0
        if age > stale_after or float(r["confidence"]) < 0.5:
            flagged.append(f"- [[{r['stem']}]] (importance {r['importance']}, confidence {r['confidence']:.2f}, {age} days)")
    out.extend(flagged[:max_items]) if flagged else out.append("- (none)")
    out.append("")

    out.append("## Decision table (apply per candidate)")
    out.append("- ADD — new information, no similar note → `brain remember --type … --if-exists new`")
    out.append("- UPDATE — same subject, more detail → `brain remember --if-exists update` (appends an Update section)")
    out.append("- SUPERSEDE — contradicts an existing note → `brain remember --supersedes <note>` (old note keeps history, status superseded)")
    out.append("- NOOP — already known or trivial → do nothing; delete the inbox item with `brain archive`")
    return "\n".join(out) + "\n"
