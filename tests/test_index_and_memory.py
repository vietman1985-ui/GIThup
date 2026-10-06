import datetime as dt
import unittest

from brain.context import build_context, format_recall
from brain.index import Index
from brain.lint import run_lint
from brain.memory import capture, consolidation_packet, log_event, recent_episodes, remember, session_end, session_prompt, session_start, session_touch
from brain.notes import parse_frontmatter

from .helpers import VaultTestCase


class IndexTests(VaultTestCase):
    def test_seed_vault_indexes_and_templates_are_hidden(self):
        with Index(self.config) as index:
            counts = index.refresh(full=True)
            self.assertGreater(counts["added"], 5)
            stats = index.stats()
            self.assertEqual(stats["broken_links"], 0, "seed vault must have no broken links")
            self.assertEqual(stats["by_type"].get("template"), 5)
            # templates never show up in search
            self.assertFalse(any(h.type == "template" for h in index.search("title", k=50)))

    def test_incremental_refresh_detects_change_and_delete(self):
        with Index(self.config) as index:
            index.refresh(full=True)
            p = self.write("wiki/Temp.md", "---\ntype: wiki\ntitle: Temp\n---\n# Temp\n\nzebra quantum\n")
            counts = index.refresh()
            self.assertEqual(counts["added"], 1)
            self.assertEqual([h.rel for h in index.search("zebra")], ["wiki/Temp.md"])
            p.write_text("---\ntype: wiki\ntitle: Temp\n---\n# Temp\n\nelephant\n", encoding="utf-8")
            import os, time
            os.utime(p, (time.time() + 5, time.time() + 5))
            counts = index.refresh()
            self.assertEqual(counts["updated"], 1)
            self.assertEqual(index.search("zebra"), [])
            self.assertEqual([h.rel for h in index.search("elephant")], ["wiki/Temp.md"])
            p.unlink()
            counts = index.refresh()
            self.assertEqual(counts["removed"], 1)
            self.assertEqual(index.search("elephant"), [])

    def test_diacritics_insensitive_search(self):
        with Index(self.config) as index:
            index.refresh()
            with_marks = {h.rel for h in index.search("bộ não", k=5)}
            without = {h.rel for h in index.search("bo nao", k=5)}
            self.assertTrue(with_marks)
            self.assertEqual(with_marks, without)

    def test_ranking_prefers_importance_and_recency(self):
        old = (dt.date.today() - dt.timedelta(days=400)).isoformat()
        new = dt.date.today().isoformat()
        self.write("memory/semantic/facts/Old low.md", f"---\ntype: fact\ntitle: Old low\nimportance: 2\ncreated: {old}\nupdated: {old}\n---\n# Old low\n\nkangaroo fact\n")
        self.write("memory/semantic/facts/New high.md", f"---\ntype: fact\ntitle: New high\nimportance: 9\ncreated: {new}\nupdated: {new}\n---\n# New high\n\nkangaroo fact\n")
        with Index(self.config) as index:
            index.refresh()
            hits = index.search("kangaroo", k=2)
            self.assertEqual(hits[0].rel, "memory/semantic/facts/New high.md")
            self.assertGreater(hits[0].score, hits[1].score)

    def test_archived_hidden_unless_requested(self):
        self.write("memory/semantic/facts/Gone.md", "---\ntype: fact\ntitle: Gone\nstatus: archived\n---\n# Gone\n\nwalrus\n")
        with Index(self.config) as index:
            index.refresh()
            self.assertEqual(index.search("walrus"), [])
            self.assertEqual([h.rel for h in index.search("walrus", include_archived=True)], ["memory/semantic/facts/Gone.md"])

    def test_links_graph_and_lint(self):
        self.write("wiki/A.md", "---\ntype: wiki\ntitle: A\ncreated: 2026-01-01\n---\n# A\n\nlinks [[B]] and [[Missing Note]] #shared\n")
        self.write("wiki/B.md", "---\ntype: wiki\ntitle: B\ncreated: 2026-01-01\n---\n# B\n\n#shared\n")
        self.write("wiki/Lonely.md", "---\ntype: wiki\ntitle: Lonely\ncreated: 2026-01-01\n---\n# Lonely\n\nnothing\n")
        with Index(self.config) as index:
            index.refresh()
            self.assertEqual(index.backlinks("wiki/B.md"), ["wiki/A.md"])
            rel = index.related("wiki/A.md")
            self.assertEqual(rel[0][0], "wiki/B.md")
            self.assertIn(("wiki/A.md", "Missing Note"), index.broken_links())
            self.assertIn("wiki/Lonely.md", index.orphans())
            issues = run_lint(self.config, index)
            codes = {(i.code, i.rel) for i in issues}
            self.assertIn(("broken-link", "wiki/A.md"), codes)
            self.assertIn(("orphan", "wiki/Lonely.md"), codes)
            self.assertFalse(any(i.rel.startswith("_templates/") for i in issues), "templates must not be linted")


class MemoryTests(VaultTestCase):
    def test_remember_add_update_supersede_noop(self):
        with Index(self.config) as index:
            path, action, _ = remember(self.config, index, "Coffee preference", "Likes black coffee.", type_="preference", tags=["#food"], importance=6)
            self.assertEqual(action, "ADD")
            self.assertTrue(path.exists())
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertEqual(fm["type"], "preference")
            self.assertEqual(fm["tags"], ["food"])
            self.assertEqual(fm["importance"], 6)

            path2, action, _ = remember(self.config, index, "Coffee preference", "Switched to espresso.", type_="preference", importance=4)
            self.assertEqual(action, "UPDATE")
            self.assertEqual(path2, path)
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertIn("## Update", body)
            self.assertIn("Switched to espresso.", body)
            self.assertEqual(fm["importance"], 6, "UPDATE keeps the higher importance")

            path3, action, _ = remember(self.config, index, "Coffee preference", "x", type_="preference", if_exists="skip")
            self.assertEqual(action, "NOOP")

            path4, action, _ = remember(self.config, index, "Tea preference", "Now drinks tea, no coffee.", type_="preference", supersedes="Coffee preference")
            self.assertEqual(action, "SUPERSEDE")
            old_fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertEqual(old_fm["status"], "superseded")
            self.assertEqual(old_fm["superseded_by"], "[[Tea preference]]")
            new_fm, new_body = parse_frontmatter(path4.read_text(encoding="utf-8"))
            self.assertEqual(new_fm["supersedes"], "[[Coffee preference]]")
            # superseded note ranks below its successor
            hits = index.search("coffee tea preference", k=5, types=["preference"])
            self.assertEqual(hits[0].rel, path4.relative_to(self.vault).as_posix())
            # the frontmatter superseded_by link counts for the graph, so lint is quiet
            codes = {i.code for i in run_lint(self.config, index)}
            self.assertNotIn("superseded-without-successor", codes)
            self.assertIn(path.relative_to(self.vault).as_posix(), index.backlinks(path4.relative_to(self.vault).as_posix()))

    def test_frontmatter_sources_count_as_links(self):
        self.write("raw/Src.md", "---\ntype: raw\ntitle: Src\ncreated: 2026-01-01\n---\n# Src\n\nevidence\n")
        self.write("wiki/Page.md", "---\ntype: wiki\ntitle: Page\ncreated: 2026-01-01\nsources: [[[Src]]]\n---\n# Page\n\nclaim\n")
        with Index(self.config) as index:
            index.refresh()
            self.assertEqual(index.backlinks("raw/Src.md"), ["wiki/Page.md"])
            codes = {(i.code, i.rel) for i in run_lint(self.config, index)}
            self.assertNotIn(("raw-uncompiled", "raw/Src.md"), codes)
            self.assertNotIn(("orphan", "wiki/Page.md"), codes)

    def test_resolve_never_escapes_the_vault(self):
        from brain.memory import resolve

        outside = self.tmp / "secret.md"
        outside.write_text("secret", encoding="utf-8")
        with Index(self.config) as index:
            index.refresh()
            self.assertIsNone(resolve(self.config, index, "../secret.md"))
            self.assertIsNone(resolve(self.config, index, str(outside)))
            self.assertIsNone(resolve(self.config, index, ".brain/index.sqlite"))
            self.assertIsNotNone(resolve(self.config, index, "[[Home|alias]]"))
            self.assertIsNotNone(resolve(self.config, index, "Home.md"))

    def test_remember_rejects_bad_type(self):
        with Index(self.config) as index:
            with self.assertRaises(ValueError):
                remember(self.config, index, "x", "y", type_="episode")

    def test_capture_and_packet(self):
        p = capture(self.config, "Ý tưởng: thêm chế độ offline\nchi tiết", tags=["idea"])
        self.assertTrue(p.exists())
        self.assertTrue(p.relative_to(self.vault).as_posix().startswith("inbox/"))
        log_event(self.config, "user said they like dark mode #remember", kind="remember")
        with Index(self.config) as index:
            packet = consolidation_packet(self.config, index, days=7)
        self.assertIn("Ý tưởng", packet)
        self.assertIn("dark mode", packet)
        self.assertIn("ADD", packet)

    def test_episodic_log_and_recent(self):
        p = log_event(self.config, "first thing")
        log_event(self.config, "second   thing\nwith newline")
        text = p.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ntype: episode"))
        self.assertIn("[note] second thing with newline", text)
        recent = recent_episodes(self.config, days=1)
        self.assertEqual(len(recent), 2)
        self.assertIn("second thing", recent[0])

    def test_session_lifecycle_writes_one_summary_line(self):
        session_start(self.config, "abc12345-xyz", "/tmp/proj", source="startup")
        session_prompt(self.config, "abc12345-xyz", "Please refactor the parser")
        session_touch(self.config, "abc12345-xyz", "/tmp/proj/src/parser.py")
        session_touch(self.config, "abc12345-xyz", "/tmp/proj/src/parser.py")  # duplicate ignored
        path = session_end(self.config, "abc12345-xyz", reason="exit")
        self.assertIsNotNone(path)
        text = path.read_text(encoding="utf-8")
        self.assertIn("session abc12345 startup in /tmp/proj", text)
        self.assertIn("ended (exit)", text)
        self.assertIn("topics: Please refactor the parser", text)
        self.assertIn("touched 1 file(s): src/parser.py", text)
        self.assertFalse(list(self.config.sessions_dir.glob("*.json")), "session state is cleaned up")

    def test_empty_session_leaves_no_trace(self):
        session_start(self.config, "empty-session", "/tmp/x", source="clear")  # 'clear' is not logged
        self.assertIsNone(session_end(self.config, "empty-session"))

    def test_duplicate_hook_firings_are_deduplicated(self):
        _, inject1 = session_start(self.config, "dup", "/tmp/x", source="startup")
        _, inject2 = session_start(self.config, "dup", "/tmp/x", source="startup")
        _, inject3 = session_start(self.config, "dup", "/tmp/x", source="compact")
        _, inject4 = session_start(self.config, "dup", "/tmp/x", source="compact")
        self.assertEqual((inject1, inject2, inject3, inject4), (True, False, True, True))
        self.assertTrue(session_prompt(self.config, "dup", "same prompt"))
        self.assertFalse(session_prompt(self.config, "dup", "same prompt"))
        self.assertTrue(session_prompt(self.config, "dup", "different prompt"))
        path = session_end(self.config, "dup")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("startup in /tmp/x"), 1, "start logged once despite two firings")
        self.assertIn("topics: same prompt; different prompt", text)


class ContextTests(VaultTestCase):
    def test_context_respects_budget_and_mentions_core_memory(self):
        with Index(self.config) as index:
            text = build_context(self.config, index, cwd="/home/user/GIThup", budget=1500)
            self.assertLessEqual(len(text), 1500)
            self.assertIn("[brain]", text)
            self.assertIn("GIThup", text)
            full = build_context(self.config, index, cwd="/somewhere/else", budget=20000)
            self.assertIn("Core memory", full)
            self.assertIn("User prefers Vietnamese", full)

    def test_format_recall_empty(self):
        self.assertEqual(format_recall([]), "")


if __name__ == "__main__":
    unittest.main()
