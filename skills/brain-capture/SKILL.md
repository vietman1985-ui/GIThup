---
name: brain-capture
description: Quick capture into the second brain's inbox — when to capture instead of remember, what to include so the item can be filed later without the conversation. Use when the user says "ghi lại", "note this", "lưu ý", "để đó", "capture", shares a link/idea/quote mid-task, or when /brain:capture is invoked.
---

# Brain capture

Capture is for *now*; filing is for the weekly review. Do not slow the user
down by asking where something belongs.

## Capture vs remember

- Use **`brain_capture`** when the item is unprocessed: an idea, a link, a
  quote, a to-do, something the user said in passing, a document to read later.
- Use **`brain_remember`** only when you already know the type, the title
  and that it is durable (a decision made, a stated preference).
- Use **`brain_log`** for "what happened" (events), not for knowledge.

## What a good inbox item contains

Pass `text` with enough context to be filed later by someone who did not see
this conversation:

```
<the thing itself — verbatim quote, URL, idea>

Why it matters: <one line>
Context: <project / person / task it came from>
Next step (if any): <…>
```

Give it a `title` the user would recognise, and `tags` for the project or
area when obvious. Reply with the created path in one short line and carry
on with the task.
