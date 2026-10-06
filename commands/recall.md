---
description: Answer a question from the second brain with citations (searches, reads, follows links, respects superseded notes).
argument-hint: <question>
---

Use the `brain-recall` skill to answer this from the user's second brain:

> $ARGUMENTS

Search with at least two phrasings (the user's words and a paraphrase; Vietnamese and English if relevant), read the top notes in full, follow backlinks one hop, prefer `status: active` notes and follow `superseded_by` chains. Answer in the user's language, end with a *Sources* line of note paths, and state confidence when notes are uncertain. If the vault has nothing relevant, say so and offer to capture the answer.
