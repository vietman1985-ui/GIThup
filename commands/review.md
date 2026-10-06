---
description: Weekly consolidation — file the inbox and episodic candidates into semantic memory, dedupe, supersede contradictions, re-score core memory, fix lint, compile sources.
argument-hint: [days=7]
---

Run the second brain's consolidation loop using the `brain-consolidate` skill. Period: $ARGUMENTS days (default 7).

Start by fetching the brief with `brain_packet` and the health report with `brain_lint`. Then:

1. File every inbox item and every `[remember]` episodic line with `brain_remember` (ADD / UPDATE / SUPERSEDE / NOOP), archiving processed inbox items.
2. Resolve duplicates and re-verify stale or low-confidence notes.
3. Keep core memory (importance ≥ 8) under ~15 notes — demote what is not needed every session.
4. Fix lint errors, then warnings. If there are more than ~10 mechanical fixes, delegate them to the `brain-librarian` agent. If any `raw-uncompiled` sources remain, delegate each to the `brain-researcher` agent.
5. Ask the `brain-critic` agent to challenge the current core memory and apply the changes it justifies with evidence.
6. Close with `brain_log` (`kind: review`) and give the user a short summary in their language: notes added / updated / superseded / archived, and anything that needs their decision.
