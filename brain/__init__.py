"""Brain — a plain-Markdown second brain that Claude (and any MCP client) can use.

Zero third-party dependencies: Python 3.8+ standard library only.
Storage is an Obsidian-compatible Markdown vault; retrieval is SQLite FTS5
(BM25) boosted by note importance, recency and the wikilink graph.
"""

__version__ = "0.1.0"
