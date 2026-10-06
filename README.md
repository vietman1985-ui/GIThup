# 🧠 Brain — bộ não thứ hai cho Claude

> Một "second brain" bằng Markdown thuần mà **Claude Code** dùng được ngay: tự nhớ, tự gợi lại, tự ghi nhật ký; tri thức được chắt lọc theo bảng quyết định ADD / UPDATE / SUPERSEDE; wiki được biên soạn từ nguồn có trích dẫn; và một "đội" model chia vai (thủ thư, củng cố, nghiên cứu, phản biện).
> **Không phụ thuộc thư viện ngoài, không cần API key, tương thích Obsidian.** Chạy offline.

[English version below](#english)

---

## Nó làm được gì

| Khả năng | Cơ chế | Mượn ý tưởng từ |
|---|---|---|
| **Nhớ tự động** — mỗi phiên Claude Code bắt đầu với "core memory" (sở thích, dự án, quyết định quan trọng) và hoạt động gần đây | hook `SessionStart` → `brain hook session-start` | claude-mem, Letta/MemGPT (core memory) |
| **Gợi lại theo từng câu hỏi** — ghi chú liên quan được chèn vào ngữ cảnh *trước khi* Claude trả lời | hook `UserPromptSubmit` → tìm kiếm FTS5, chỉ chèn khi điểm đủ cao | claude-mem, mem0 |
| **Nhật ký episodic** — phiên nào, làm gì, sửa file nào, ghi về `memory/episodic/YYYY-MM-DD.md` | hook `PostToolUse` + `SessionEnd`, một dòng mỗi phiên | Generative Agents (observation stream) |
| **Bộ nhớ ngữ nghĩa có lịch sử** — fact / entity / decision / preference / procedure, mỗi ghi chú một ý, có `importance`, `confidence`, `status` | `brain remember` với ADD / UPDATE / SUPERSEDE / NOOP; không bao giờ ghi đè, chỉ `superseded` | mem0 (decision table), Graphiti (temporal validity) |
| **Wiki biên soạn từ nguồn** — `raw/` bất biến → `wiki/` có trích dẫn từng ý | skill `brain-wiki`, lint `raw-uncompiled` | Karpathy LLM-wiki, claude-obsidian, llm-wiki-agent |
| **Tìm kiếm không cần vector DB** — BM25 (SQLite FTS5) × importance × độ mới; **không dấu vẫn tìm ra có dấu** ("bo nao" → "bộ não") | `brain/index.py` | — |
| **Đội model chia vai** — `brain-librarian` (haiku, việc máy móc), `brain-consolidator` (sonnet, củng cố), `brain-researcher` (biên soạn), `brain-critic` (opus, phản biện) | `agents/*.md` | kiến trúc "não giả lập qua trung gian các model" |
| **Dùng được từ mọi client MCP** — Claude Desktop, Cursor, v.v. | `brain mcp` (JSON-RPC stdio, 12 tool) | basic-memory, OpenMemory |
| **Kiểm tra sức khỏe** — link hỏng, ghi chú mồ côi, trùng tiêu đề, fact cũ, inbox tồn | `brain lint` | llm-wiki-agent |

## Cài đặt (2 phút)

Yêu cầu: Python ≥ 3.8 (có sẵn trên macOS/Linux; Windows cài từ python.org) và Claude Code.

**Cách 1 — cài như plugin Claude Code (khuyên dùng):**

```text
/plugin marketplace add vietman1985-ui/GIThup
/plugin install brain@githup
```

Khởi động lại Claude Code — xong. Vault cá nhân được tạo tự động ở `~/.brain/vault` trong lần dùng đầu tiên (gồm `_schema.md` và template, chưa có ghi chú). Muốn lấy luôn vault mẫu của repo (có khảo sát + ví dụ):

```bash
git clone https://github.com/vietman1985-ui/GIThup.git
BRAIN_VAULT=~/.brain/vault python3 GIThup/bin/brain init
```

Windows: cài Python từ python.org hoặc Microsoft Store (có sẵn lệnh `python3`), rồi làm y hệt trong PowerShell.

**Cách 2 — dùng thử không cài:**

```bash
git clone https://github.com/vietman1985-ui/GIThup.git && cd GIThup
claude --plugin-dir .        # vault mẫu trong ./vault được dùng nhờ .brain.toml
```

Chỉ mở repo bằng `claude` (không có `--plugin-dir`) cũng đã có MCP server (`.mcp.json`) và các hook bộ nhớ (`.claude/settings.json`); nhưng lệnh `/brain:…` và các agent chỉ xuất hiện khi plugin được nạp.

**Cách 3 — chỉ dùng CLI / MCP (không cần Claude Code):**

```bash
pip install -e .             # hoặc: uv tool install .
brain init && brain doctor
claude mcp add brain -- brain mcp          # hoặc thêm vào Claude Desktop config
```

## Dùng hằng ngày

Trong Claude Code, sau khi cài plugin:

| Lệnh | Việc |
|---|---|
| `/brain:recall <câu hỏi>` | Trả lời từ bộ não, có trích dẫn đường dẫn ghi chú |
| `/brain:remember <điều cần nhớ>` | Lưu fact / quyết định / sở thích (tự kiểm tra trùng, chọn ADD/UPDATE/SUPERSEDE) |
| `/brain:capture <ý tưởng, link>` | Ghi nhanh vào inbox, xử lý sau |
| `/brain:review` | Tổng hợp hằng tuần: inbox → semantic, khử trùng, chấm lại importance, lint, biên soạn wiki |
| `/brain:compile <nguồn>` | Biến tài liệu/URL thành trang wiki có trích dẫn |
| `/brain:lint` · `/brain:status` · `/brain:forget` | Sức khỏe vault · tình trạng · cho một ghi chú "nghỉ hưu" (archive/supersede, không xóa) |

Hoặc chỉ cần nói chuyện bình thường — skill `brain` tự kích hoạt khi bạn nói "nhớ", "ghi lại", "hôm trước mình quyết định gì", v.v.

CLI tương đương (`python3 bin/brain …` hoặc `brain …` nếu đã `pip install`):

```bash
brain search "quyết định về database" -k 5        # tìm
brain recall "người dùng thích ngôn ngữ nào"        # tìm + định dạng thành ngữ cảnh
brain read "[[GIThup brain project]]" --meta        # đọc + backlinks + related
brain remember "Minh (frontend lead)" "Phụ trách UI, thích Tailwind." --type entity --importance 6
brain remember "Decision - dùng Postgres" "Thay cho MySQL vì cần JSONB." --type decision --supersedes "Decision - dùng MySQL"
brain capture "Đọc bài về Graphiti https://…"
brain log "họp với A, chốt deadline 20/10" --kind decision
brain packet --days 7 && brain lint && brain stats
```

## Cấu trúc vault

```
vault/
├── Home.md                 # map of content — điểm vào
├── _schema.md              # chuẩn frontmatter (type, importance, confidence, status, supersedes…)
├── _templates/
├── inbox/                  # ghi nhanh chưa xử lý
├── memory/
│   ├── episodic/           # nhật ký theo ngày, chỉ ghi thêm (hook tự viết)
│   ├── semantic/           # facts/ entities/ decisions/ preferences/ — mỗi ghi chú một ý
│   └── procedural/         # quy trình đã học
├── wiki/                   # trang tổng hợp, mỗi ý có trích dẫn [[raw/…]]
├── raw/                    # nguồn gốc, bất biến
└── .brain/                 # index SQLite (cache, git-ignore)
```

Mở thư mục `vault/` bằng Obsidian là có graph view, backlinks… đầy đủ.

### Vault nằm ở đâu?

Thứ tự: biến môi trường `BRAIN_VAULT` → file `.brain.toml` gần nhất (repo này trỏ vào `./vault`) → `~/.brain/vault` (tự tạo khi chưa có). `brain where` cho biết đang dùng vault nào. Bạn có thể đặt vault trong một repo git riêng để đồng bộ nhiều máy, hoặc trỏ `BRAIN_VAULT` vào vault Obsidian sẵn có.

## Tốt hơn các repo đang có ở điểm nào

Khảo sát 282 repo "second brain" trên GitHub (06/10/2026) nằm trong `vault/raw/` và được tổng hợp ở `vault/wiki/Second brain landscape 2026.md`. Rút ra:

1. **Không cần API key hay vector DB** — mem0, Zep, Khoj, Letta đều cần một trong hai để chạy. Ở đây chỉ cần `python3`.
2. **Nhớ là tự động, không cần model "nhớ ra phải tìm"** — các bộ skill (second-brain-os, obsidian-second-brain) dựa vào việc model tự gọi lệnh; ở đây hook chèn ghi chú liên quan trước mỗi prompt.
3. **Không mất lịch sử** — fact thay đổi thì `superseded`, không ghi đè (ý của Graphiti), nhưng vẫn là Markdown đọc được.
4. **Nhỏ, đọc hết được trong một buổi** — ~1.500 dòng Python chuẩn, test thuần `unittest`, không build step. Dự án chết thì bạn fork là xong.
5. **Chia vai theo chi phí** — việc máy móc chạy bằng model rẻ (haiku), phản biện bằng model mạnh (opus).

## Phát triển

```bash
python3 -m unittest discover -s tests -t . -v     # test thuần unittest, không cần cài gì
claude plugin validate . && claude plugin validate skills --strict
python3 bin/brain lint --strict                   # vault mẫu phải sạch lỗi
```

CI (`.github/workflows/ci.yml`) chạy test trên Python 3.8 / 3.11 / 3.13 và validate plugin.

---

## English

**Brain** is a plain-Markdown second brain that Claude Code uses through a plugin (skills, slash commands, subagents, hooks) and an MCP server. Standard library only, no API key, Obsidian-compatible, works offline.

- **Automatic memory:** `SessionStart` injects core memory + recent activity; `UserPromptSubmit` injects notes relevant to each prompt; `PostToolUse`/`SessionEnd` write one episodic line per session.
- **Semantic memory with history:** `brain remember` applies ADD / UPDATE / SUPERSEDE / NOOP; nothing is overwritten, old notes become `status: superseded` with a `superseded_by` link (Graphiti-style temporal validity).
- **LLM-wiki:** immutable `raw/` sources → cited `wiki/` pages; lint flags uncompiled sources, broken links, orphans, stale facts.
- **Retrieval without a vector DB:** SQLite FTS5 BM25 × importance × recency, diacritics-insensitive.
- **Role-split agents:** `brain-librarian` (haiku), `brain-consolidator` (sonnet), `brain-researcher`, `brain-critic` (opus).
- **MCP server:** `brain mcp` exposes 12 tools (`brain_search`, `brain_read`, `brain_remember`, `brain_capture`, `brain_log`, `brain_related`, `brain_context`, `brain_lint`, `brain_packet`, `brain_set_status`, `brain_list`, `brain_stats`) to any MCP client.

Install: `/plugin marketplace add vietman1985-ui/GIThup` then `/plugin install brain@githup`, restart, run `brain init`. Or try it with `claude --plugin-dir .` inside a clone. Commands: `/brain:recall`, `/brain:remember`, `/brain:capture`, `/brain:review`, `/brain:compile`, `/brain:lint`, `/brain:status`, `/brain:forget`.

License: MIT.
