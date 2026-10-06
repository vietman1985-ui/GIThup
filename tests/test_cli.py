import json
import os
import subprocess
import sys
import unittest

from .helpers import REPO_ROOT, VaultTestCase

BRAIN = [sys.executable, str(REPO_ROOT / "bin" / "brain")]


class CliTests(VaultTestCase):
    def run_brain(self, *args, input=None, check=True):
        env = dict(os.environ, BRAIN_VAULT=str(self.vault))
        r = subprocess.run(BRAIN + list(args), input=input, capture_output=True, text=True, env=env, cwd=str(self.tmp))
        if check:
            self.assertEqual(r.returncode, 0, f"{args}: {r.stderr}")
        return r

    def test_end_to_end(self):
        self.assertIn(str(self.vault), self.run_brain("where").stdout)
        self.run_brain("index", "--full")
        stats = json.loads(self.run_brain("stats", "--json").stdout)
        self.assertGreater(stats["notes"], 5)
        self.assertEqual(stats["broken_links"], 0)

        out = self.run_brain("remember", "CLI fact", "Stored from the command line.", "--type", "fact", "--tags", "cli,test", "--importance", "7").stdout
        self.assertIn("ADD: memory/semantic/facts/CLI fact.md", out)
        out = self.run_brain("remember", "CLI fact", "-", "--stdin", input="More detail via stdin.").stdout
        self.assertIn("UPDATE:", out)
        text = self.run_brain("read", "CLI fact").stdout
        self.assertIn("More detail via stdin.", text)

        hits = json.loads(self.run_brain("search", "stored command line", "--json").stdout)
        self.assertEqual(hits[0]["rel"], "memory/semantic/facts/CLI fact.md")
        self.assertIn("CLI fact", self.run_brain("recall", "command line").stdout)

        self.assertIn("captured: inbox/", self.run_brain("capture", "quick idea", "--title", "Idea").stdout)
        self.assertIn("logged:", self.run_brain("log", "did a thing", "--kind", "decision").stdout)
        self.assertIn("inbox-backlog", self.run_brain("lint").stdout)
        self.assertIn("Consolidation packet", self.run_brain("packet").stdout)
        self.assertIn("→ archived", self.run_brain("archive", "CLI fact").stdout)
        rels = [h["rel"] for h in json.loads(self.run_brain("search", "stored command line", "--json").stdout)]
        self.assertNotIn("memory/semantic/facts/CLI fact.md", rels, "archived notes are hidden")
        rels = [h["rel"] for h in json.loads(self.run_brain("search", "stored command line", "--all", "--json").stdout)]
        self.assertIn("memory/semantic/facts/CLI fact.md", rels)
        self.assertIn("[brain]", self.run_brain("context", "--cwd", "/x").stdout)
        self.assertIn("all good", self.run_brain("doctor").stdout)

    def test_missing_vault_is_a_clear_error(self):
        env = dict(os.environ, BRAIN_VAULT=str(self.tmp / "nope"))
        r = subprocess.run(BRAIN + ["stats"], capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 3)
        self.assertIn("brain init", r.stderr)

    def test_init_from_scratch(self):
        env = dict(os.environ, BRAIN_VAULT=str(self.tmp / "fresh"))
        r = subprocess.run(BRAIN + ["init", "--no-template"], capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "fresh" / "Home.md").exists())
        self.assertTrue((self.tmp / "fresh" / "memory" / "semantic" / "facts").is_dir())
        self.assertTrue((self.tmp / "fresh" / ".gitignore").exists())
        # a brand-new vault must be lint-clean (no broken links in the generated Home.md)
        r = subprocess.run(BRAIN + ["lint", "--strict"], capture_output=True, text=True, env=env, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("[error]", r.stdout)


if __name__ == "__main__":
    unittest.main()
