---
type: moc
title: Home
created: 2026-10-06
updated: 2026-10-06
importance: 10
tags: [moc, pinned]
---

# Home

Bản đồ nội dung (map of content) của bộ não này. Bắt đầu từ đây.

## Bộ nhớ (memory)

- **Episodic** — nhật ký theo ngày, chỉ ghi thêm: `memory/episodic/YYYY-MM-DD.md`
- **Semantic** — tri thức đã chắt lọc, mỗi ghi chú một ý:
  - sự kiện/dữ kiện: `memory/semantic/facts/` — ví dụ [[Brain uses SQLite FTS5 for retrieval]]
  - thực thể (người, dự án, công cụ): `memory/semantic/entities/` — ví dụ [[GIThup brain project]]
  - quyết định: `memory/semantic/decisions/` — ví dụ [[Decision - build on Markdown plus SQLite, no vector DB]]
  - sở thích/ưu tiên của người dùng: `memory/semantic/preferences/` — ví dụ [[User prefers Vietnamese]]
- **Procedural** — quy trình đã học: `memory/procedural/` — ví dụ [[How to run a weekly brain review]]

## Tri thức (knowledge)

- **Wiki** — trang tổng hợp có trích dẫn nguồn: `wiki/` — ví dụ [[Second brain landscape 2026]]
- **Raw** — nguồn gốc, không sửa tay: `raw/` — ví dụ [[second-brain-repos-survey-2026-10-06]]

## Inbox

- Ghi nhanh chưa xử lý: `inbox/` → xử lý bằng `/brain:review`

## Quy ước

- Xem [[_schema]] để biết frontmatter chuẩn (type, importance, confidence, status...).
- Ghi chú mới: `brain remember` (semantic) hoặc `brain capture` (inbox).
- Không bao giờ sửa file trong `raw/`; tri thức rút ra đi vào `wiki/` và trích dẫn ngược lại.
