"""Markdown note model: frontmatter, wikilinks, tags.

Notes are plain Markdown files with an optional YAML frontmatter block.  We
only need a small, predictable subset of YAML, so the parser here is
deliberately simple:

* ``key: value`` scalars (strings, ints, floats, booleans, ISO dates)
* inline lists ``key: [a, b, c]``
* block lists::

      key:
        - a
        - b

Anything else is kept as a raw string so round-tripping never loses data.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(?P<fm>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
# [[target]], [[target|alias]], [[target#heading]], ![[embed]]
WIKILINK_RE = re.compile(r"!?\[\[(?P<target>[^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
# #tag in body text (not inside code, not a heading marker, not a URL fragment)
TAG_RE = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=\())#(?P<tag>[A-Za-z0-9_\-/À-ɏḀ-ỿ]+)", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

NOTE_TYPES = (
    "inbox",
    "episode",
    "fact",
    "entity",
    "decision",
    "preference",
    "procedure",
    "wiki",
    "raw",
    "moc",
    "template",
)

STATUSES = ("active", "superseded", "archived", "draft")


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw == "" or raw in ("~", "null", "Null", "NULL"):
        return None
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    low = raw.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if re.fullmatch(r"[+-]?\d+", raw):
        try:
            return int(raw)
        except ValueError:
            return raw
    if re.fullmatch(r"[+-]?\d*\.\d+", raw):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def _parse_inline_list(raw: str) -> List[Any]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    items: List[Any] = []
    buf = ""
    quote: Optional[str] = None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(_parse_scalar(buf))
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(_parse_scalar(buf))
    return items


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Return ``(frontmatter_dict, body)``.  Missing frontmatter -> ``({}, text)``."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group("fm")
    body = text[m.end():]
    data: Dict[str, Any] = {}
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # block list or empty
            items: List[Any] = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s+-\s*", lines[j]):
                items.append(_parse_scalar(re.sub(r"^\s+-\s*", "", lines[j])))
                j += 1
            if j > i + 1:
                data[key] = items
                i = j
                continue
            data[key] = None
        elif rest.startswith("[") and rest.endswith("]"):
            data[key] = _parse_inline_list(rest)
        else:
            data[key] = _parse_scalar(rest)
        i += 1
    return data, body


def _dump_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    s = str(value)
    if s == "" or re.search(r"[:#\[\]{}\n\"']", s) or s.strip() != s or s.lower() in ("true", "false", "null", "yes", "no"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def dump_frontmatter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}: [{', '.join(_dump_scalar(v) for v in value)}]")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def strip_code(body: str) -> str:
    body = CODE_FENCE_RE.sub(" ", body)
    return INLINE_CODE_RE.sub(" ", body)


def extract_wikilinks(body: str, frontmatter: Optional[Dict[str, Any]] = None) -> List[str]:
    """Wikilinks in the body plus in frontmatter values (``sources``,
    ``supersedes``, ``superseded_by``, …) so they count for the graph."""
    seen: List[str] = []

    def scan(text: str) -> None:
        for m in WIKILINK_RE.finditer(text):
            target = m.group("target").strip()
            if target and target not in seen:
                seen.append(target)

    scan(strip_code(body))
    for value in (frontmatter or {}).values():
        if isinstance(value, str):
            scan(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    scan(item)
    return seen


def extract_tags(body: str, frontmatter: Optional[Dict[str, Any]] = None) -> List[str]:
    tags: List[str] = []
    if frontmatter:
        raw = frontmatter.get("tags")
        if isinstance(raw, str):
            raw = [t for t in re.split(r"[,\s]+", raw) if t]
        for t in raw or []:
            t = str(t).strip().lstrip("#")
            if t and t not in tags:
                tags.append(t)
    for m in TAG_RE.finditer(strip_code(body)):
        t = m.group("tag").strip("/-_")
        # pure numbers are not tags (e.g. "#1" issue references)
        if t and not t.isdigit() and t not in tags:
            tags.append(t)
    return tags


def first_heading(body: str) -> Optional[str]:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def slugify(title: str, max_len: int = 80) -> str:
    """Filesystem- and Obsidian-safe filename stem that keeps Vietnamese letters."""
    title = unicodedata.normalize("NFC", title.strip())
    title = re.sub(r"[\\/:*?\"<>|#\[\]^]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title or "untitled"


def today() -> str:
    return _dt.date.today().isoformat()


def now_hm() -> str:
    return _dt.datetime.now().strftime("%H:%M")


@dataclass
class Note:
    path: Path  # absolute path
    rel: str  # path relative to vault root, with forward slashes
    frontmatter: Dict[str, Any]
    body: str
    title: str
    type: str
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def importance(self) -> int:
        try:
            return max(0, min(10, int(self.frontmatter.get("importance", 5))))
        except (TypeError, ValueError):
            return 5

    @property
    def confidence(self) -> float:
        try:
            return max(0.0, min(1.0, float(self.frontmatter.get("confidence", 0.8))))
        except (TypeError, ValueError):
            return 0.8

    @property
    def status(self) -> str:
        s = str(self.frontmatter.get("status") or "active").lower()
        return s if s in STATUSES else "active"

    @property
    def created(self) -> str:
        return str(self.frontmatter.get("created") or "")

    @property
    def updated(self) -> str:
        return str(self.frontmatter.get("updated") or self.created or "")

    def summary(self, max_len: int = 160) -> str:
        """First meaningful body line, trimmed — used in context packets."""
        for line in self.body.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("---") or s.startswith("<!--"):
                continue
            s = re.sub(r"^[-*+]\s+", "", s)
            s = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", lambda m: m.group(2) or m.group(1), s)
            if len(s) > max_len:
                s = s[: max_len - 1].rstrip() + "…"
            return s
        return ""


def infer_type(rel: str, frontmatter: Dict[str, Any]) -> str:
    # Templates carry the frontmatter of the note they will become, so the
    # folder wins over the declared type for them.
    if rel.startswith("_templates/"):
        return "template"
    t = str(frontmatter.get("type") or "").lower()
    if t in NOTE_TYPES:
        return t
    if rel.startswith("inbox/"):
        return "inbox"
    if rel.startswith("memory/episodic/"):
        return "episode"
    if rel.startswith("memory/procedural/"):
        return "procedure"
    if rel.startswith("memory/semantic/decisions/"):
        return "decision"
    if rel.startswith("memory/semantic/preferences/"):
        return "preference"
    if rel.startswith("memory/semantic/"):
        return "fact"
    if rel.startswith("wiki/"):
        return "wiki"
    if rel.startswith("raw/"):
        return "raw"
    if rel.startswith("_templates/"):
        return "template"
    return "wiki"


def load_note(vault: Path, path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    rel = path.relative_to(vault).as_posix()
    title = str(fm.get("title") or first_heading(body) or path.stem)
    return Note(
        path=path,
        rel=rel,
        frontmatter=fm,
        body=body,
        title=title,
        type=infer_type(rel, fm),
        tags=extract_tags(body, fm),
        links=extract_wikilinks(body, fm),
    )


def iter_note_paths(vault: Path) -> Iterable[Path]:
    for p in sorted(vault.rglob("*.md")):
        parts = p.relative_to(vault).parts
        if any(part.startswith(".") for part in parts):
            continue  # skip .brain/, .obsidian/, .git/
        yield p


def render_note(frontmatter: Dict[str, Any], body: str) -> str:
    return dump_frontmatter(frontmatter) + ("\n" if not body.startswith("\n") else "") + body.rstrip("\n") + "\n"
