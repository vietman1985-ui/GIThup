"""Vault discovery and configuration.

Resolution order for the vault directory:

1. ``BRAIN_VAULT`` environment variable.
2. The nearest ancestor of the current directory (or of ``start``) that
   contains a ``.brain.toml`` file; its ``vault`` key (default ``"vault"``)
   is resolved relative to that file.
3. ``~/.brain/vault`` (created on demand by ``brain init``).

``.brain.toml`` is parsed with a tiny TOML-subset parser so the tool keeps
working on Python versions without ``tomllib``.  Only ``key = value`` pairs
(strings, integers, floats, booleans) and ``[section]`` headers are supported,
which is all the brain needs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_FILENAME = ".brain.toml"
INDEX_DIRNAME = ".brain"

# Sub-directories every vault has.  Keeping them here means the CLI, the
# hooks, the MCP server and the tests all agree on the layout.
VAULT_DIRS = (
    "inbox",
    "memory/episodic",
    "memory/semantic",
    "memory/procedural",
    "wiki",
    "raw",
    "_templates",
)

DEFAULTS: Dict[str, Any] = {
    # How many characters of context the SessionStart hook may inject.
    "context_budget": 2400,
    # How many notes the UserPromptSubmit hook may surface per prompt.
    "recall_k": 3,
    # Minimum score a recalled note needs before it is injected into a prompt.
    "recall_min_score": 1.0,
    # Whether the UserPromptSubmit hook injects recalled notes at all.
    "auto_recall": True,
    # Whether hooks write to the episodic log.
    "auto_log": True,
    # Recency half-life (days) used when ranking search results.
    "recency_half_life_days": 30,
    # Notes with status 'active' older than this many days are flagged by lint.
    "stale_after_days": 180,
}


@dataclass
class Config:
    vault: Path
    source: str  # where the vault path came from, for diagnostics
    settings: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS))

    @property
    def index_dir(self) -> Path:
        return self.vault / INDEX_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.index_dir / "index.sqlite"

    @property
    def sessions_dir(self) -> Path:
        return self.index_dir / "sessions"

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, DEFAULTS.get(key, default))


_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
_KV_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_.-]+)\s*=\s*(?P<value>.+?)\s*$")


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    # strip trailing comment that is not inside quotes
    if not (raw.startswith('"') or raw.startswith("'")):
        raw = raw.split("#", 1)[0].strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return bytes(raw[1:-1], "utf-8").decode("unicode_escape")
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        if re.fullmatch(r"[+-]?\d+", raw):
            return int(raw)
        if re.fullmatch(r"[+-]?\d*\.\d+([eE][+-]?\d+)?", raw):
            return float(raw)
    except ValueError:
        pass
    return raw


def parse_toml_subset(text: str) -> Dict[str, Any]:
    """Parse the ``key = value`` / ``[section]`` subset of TOML we rely on.

    Section keys are flattened as ``section.key``.
    """
    out: Dict[str, Any] = {}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _SECTION_RE.match(line)
        if m:
            section = m.group("name").strip()
            continue
        m = _KV_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        full = f"{section}.{key}" if section else key
        out[full] = _parse_scalar(m.group("value"))
    return out


def find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        cfg = candidate / CONFIG_FILENAME
        if cfg.is_file():
            return cfg
    return None


def load_config(start: Optional[Path] = None, vault_override: Optional[str] = None) -> Config:
    settings: Dict[str, Any] = dict(DEFAULTS)
    cfg_file = find_config_file(start)
    cfg_values: Dict[str, Any] = {}
    if cfg_file is not None:
        try:
            cfg_values = parse_toml_subset(cfg_file.read_text(encoding="utf-8"))
        except OSError:
            cfg_values = {}
        for key, value in cfg_values.items():
            # accept both top-level keys and [brain] section keys
            name = key.split(".", 1)[1] if key.startswith("brain.") else key
            if name in DEFAULTS:
                settings[name] = value

    if vault_override:
        return Config(Path(vault_override).expanduser().resolve(), "argument", settings)

    env_vault = os.environ.get("BRAIN_VAULT")
    if env_vault:
        return Config(Path(env_vault).expanduser().resolve(), "BRAIN_VAULT", settings)

    if cfg_file is not None:
        rel = cfg_values.get("vault", cfg_values.get("brain.vault", "vault"))
        vault = (cfg_file.parent / str(rel)).resolve()
        return Config(vault, str(cfg_file), settings)

    home = Path(os.environ.get("BRAIN_HOME", Path.home() / ".brain")).expanduser()
    return Config((home / "vault").resolve(), "default (~/.brain/vault)", settings)
