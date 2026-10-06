"""Shared fixtures for the test-suite (stdlib unittest only)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from brain.config import Config, DEFAULTS
from brain.memory import init_vault

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_VAULT = REPO_ROOT / "vault"


class VaultTestCase(unittest.TestCase):
    """Creates a fresh temporary vault seeded from the repo's example vault."""

    seed = True

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="brain-test-"))
        self.vault = self.tmp / "vault"
        self.config = Config(self.vault, "test", dict(DEFAULTS))
        init_vault(self.config, template_dir=SEED_VAULT if self.seed else None)
        self._old_env = {k: os.environ.get(k) for k in ("BRAIN_VAULT", "BRAIN_DEBUG")}
        os.environ["BRAIN_VAULT"] = str(self.vault)

    def tearDown(self) -> None:
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> Path:
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p
