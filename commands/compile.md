---
description: Compile a raw source (or a topic) into a cited wiki page in the second brain — LLM-wiki pattern.
argument-hint: <raw note path, URL, or topic>
---

Compile this into the second brain's wiki using the `brain-wiki` skill:

> $ARGUMENTS

If the argument is a URL or pasted material, first store it unmodified as a `raw/` note (type `raw`, with `source`). Then read it, search for existing wiki pages on the topic, and write or update the page with `brain_remember {type: "wiki"}` — Summary, Details with a citation on every claim, Open questions, Sources. Create entity/fact notes for things that will be asked about on their own, link the page from `Home.md` or a topic MOC, run `brain_lint`, and log the compilation. Report the pages created or updated.
