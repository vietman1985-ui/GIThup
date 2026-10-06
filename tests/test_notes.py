import unittest

from brain.notes import (
    dump_frontmatter,
    extract_tags,
    extract_wikilinks,
    infer_type,
    parse_frontmatter,
    render_note,
    slugify,
)


class FrontmatterTests(unittest.TestCase):
    def test_parse_scalars_lists_and_body(self):
        text = (
            "---\n"
            "type: fact\n"
            "title: \"Quoted: title\"\n"
            "tags: [a, b-c, \"d e\"]\n"
            "importance: 7\n"
            "confidence: 0.75\n"
            "status: active\n"
            "sources:\n"
            "  - raw/x.md\n"
            "  - https://example.com\n"
            "flag: true\n"
            "empty:\n"
            "---\n"
            "\n# Heading\n\nbody\n"
        )
        fm, body = parse_frontmatter(text)
        self.assertEqual(fm["type"], "fact")
        self.assertEqual(fm["title"], "Quoted: title")
        self.assertEqual(fm["tags"], ["a", "b-c", "d e"])
        self.assertEqual(fm["importance"], 7)
        self.assertAlmostEqual(fm["confidence"], 0.75)
        self.assertEqual(fm["sources"], ["raw/x.md", "https://example.com"])
        self.assertIs(fm["flag"], True)
        self.assertIsNone(fm["empty"])
        self.assertTrue(body.lstrip().startswith("# Heading"))

    def test_no_frontmatter(self):
        fm, body = parse_frontmatter("# Just a heading\n")
        self.assertEqual(fm, {})
        self.assertEqual(body, "# Just a heading\n")

    def test_roundtrip(self):
        fm = {"type": "fact", "title": "A: B", "tags": ["x", "y"], "importance": 5, "ok": True, "score": 0.5}
        text = render_note(fm, "# A: B\n\nbody")
        parsed, body = parse_frontmatter(text)
        self.assertEqual(parsed, fm)
        self.assertEqual(body.strip(), "# A: B\n\nbody")

    def test_dump_quotes_special_values(self):
        out = dump_frontmatter({"title": "yes", "other": "has # hash"})
        self.assertIn('title: "yes"', out)
        self.assertIn('other: "has # hash"', out)


class ExtractionTests(unittest.TestCase):
    def test_wikilinks_with_alias_heading_embed_and_code(self):
        body = "See [[Target One]] and [[Two|alias]] and [[Three#Sec]] ![[img.png]] `[[not a link]]`\n```\n[[also not]]\n```"
        self.assertEqual(extract_wikilinks(body), ["Target One", "Two", "Three", "img.png"])

    def test_tags_from_body_and_frontmatter(self):
        tags = extract_tags("Text #alpha and #beta/gamma, not#inline and #123 issue (#paren)", {"tags": ["fm", "alpha"]})
        self.assertEqual(tags, ["fm", "alpha", "beta/gamma", "paren"])

    def test_vietnamese_tags(self):
        self.assertIn("bộ-não", extract_tags("về #bộ-não thứ hai"))

    def test_infer_type(self):
        self.assertEqual(infer_type("_templates/fact.md", {"type": "fact"}), "template")
        self.assertEqual(infer_type("memory/semantic/facts/x.md", {}), "fact")
        self.assertEqual(infer_type("memory/semantic/decisions/x.md", {}), "decision")
        self.assertEqual(infer_type("memory/episodic/2026-01-01.md", {}), "episode")
        self.assertEqual(infer_type("wiki/x.md", {"type": "entity"}), "entity")
        self.assertEqual(infer_type("anything/else.md", {}), "wiki")

    def test_slugify_keeps_vietnamese_and_strips_unsafe(self):
        self.assertEqual(slugify("Bộ não: thứ hai / 2026?"), "Bộ não thứ hai 2026")
        self.assertEqual(slugify("   "), "untitled")


if __name__ == "__main__":
    unittest.main()
