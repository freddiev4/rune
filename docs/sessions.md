# Sessions

## Overview

A **session** is the unit of state for a single agent interaction. It holds the full conversation history (messages, tool calls, tool results), token usage, working directory, and parent/child relationships for subagent trees.

Sessions are automatically persisted to a SQLite database at `~/.rune/sessions.db` after every turn. They can be listed, resumed, and inspected from the CLI or Python API.

---

## Data Model

### `Session`

Defined in `rune/harness/session.py`.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | 8-character UUID prefix, e.g. `"a3f9c1b2"` |
| `parent_session_id` | `str \| None` | Set when forked for a subagent |
| `child_session_ids` | `list[str]` | Populated at load time from the DB |
| `working_dir` | `str` | `os.getcwd()` at agent creation |
| `system_prompt` | `str` | The full system prompt used by this session |
| `messages` | `list[Message]` | All messages including system, user, assistant, tool |
| `created_at` | `datetime` | When the session was created |
| `turn_count` | `int` | Number of user messages added |
| `usage` | `UsageStats` | Cumulative prompt/completion/total token counts |

### `Message`

| Field | Type | Description |
|-------|------|-------------|
| `role` | `str` | `"system"`, `"user"`, `"assistant"`, or `"tool"` |
| `content` | `str \| None` | Text content |
| `tool_calls` | `list[dict] \| None` | Tool call requests (assistant role) |
| `tool_call_id` | `str \| None` | Which tool call this is a result for (tool role) |
| `name` | `str \| None` | Tool name (tool role) |

### `UsageStats`

Tracks cumulative token usage across all API calls in the session.

| Field | Type |
|-------|------|
| `prompt_tokens` | `int` |
| `completion_tokens` | `int` |
| `total_tokens` | `int` |

---

## SQLite Storage

### Database location

```
~/.rune/sessions.db
```

Created automatically on first use. The directory `~/.rune/` is created if it does not exist.

### Schema

```sql
CREATE TABLE sessions (
    session_id        TEXT PRIMARY KEY,
    parent_session_id TEXT REFERENCES sessions(session_id),
    working_dir       TEXT NOT NULL,
    system_prompt     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,   -- ISO-8601 UTC
    updated_at        TEXT NOT NULL,   -- ISO-8601 UTC, updated on every save
    turn_count        INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    title             TEXT             -- first user message, truncated to 60 chars
);

CREATE INDEX idx_sessions_updated_at ON sessions(updated_at DESC);

CREATE TABLE messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT    NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    msg_order     INTEGER NOT NULL,
    role          TEXT    NOT NULL,
    content       TEXT,
    tool_calls    TEXT,               -- JSON-encoded list, NULL if none
    tool_call_id  TEXT,
    name          TEXT,
    UNIQUE(session_id, msg_order)
);

CREATE INDEX idx_messages_session ON messages(session_id, msg_order);
```

**Schema versioning:** `PRAGMA user_version` is set to `1`. Future migrations increment this value and apply incremental changes.

**Session title:** Derived once from the first user message (first 60 chars, newlines stripped). Never overwritten on subsequent saves — the `COALESCE(sessions.title, excluded.title)` upsert pattern preserves the original title.

**Message storage:** All messages are deleted and re-inserted on every save. This is simpler than diffing and fast enough for typical session sizes.

---

## Auto-save Behaviour

The `Agent` class (in `rune/harness/agent.py`) automatically saves after:

1. **Agent initialisation** — registers the session in the DB immediately.
2. **Every turn** — saved after each `yield TurnResult(...)` in `Agent.stream()`, regardless of whether the turn had tool calls.
3. **Shutdown** — saved in `Agent.shutdown()` before closing the DB connection.

Subagents share the parent's `SessionStore` instance. Their sessions are saved on the same schedule as root sessions, linked by `parent_session_id`.

To disable persistence:

```python
agent = Agent(config=AgentConfig(use_store=False))
```

---

## Subagent Session Graph

When the `task` tool spawns a subagent, `Session.fork()` creates a child session with `parent_session_id` set to the parent's `session_id`. The child is saved to the same DB using the shared store instance.

This creates a directed tree rooted at the original session:

```
abc12345  "implement auth feature"      turns=12
├── def67890  "write JWT middleware"    turns=8
└── ghi11223  "write auth tests"       turns=5
    └── jkl44556  "fix failing test"   turns=3
```

Querying the full tree uses a recursive CTE:

```sql
WITH RECURSIVE tree AS (
    SELECT session_id, parent_session_id, title, working_dir,
           created_at, updated_at, turn_count, 0 AS depth
    FROM sessions WHERE session_id = ?
    UNION ALL
    SELECT s.session_id, s.parent_session_id, s.title, s.working_dir,
           s.created_at, s.updated_at, s.turn_count, t.depth + 1
    FROM sessions s JOIN tree t ON s.parent_session_id = t.session_id
)
SELECT * FROM tree ORDER BY depth, created_at;
```

---

## CLI

### List recent sessions

```bash
rune --list-sessions
```

Prints a Rich table ordered by most recently updated:

```
         Recent Sessions
┌──────────┬────────────────────────┬─────────────┬──────────────────────┬───────┐
│ ID       │ Title                  │ Directory   │ Updated              │ Turns │
├──────────┼────────────────────────┼─────────────┼──────────────────────┼───────┤
│ abc12345 │ implement auth feature │ ~/myproject │ 2026-02-26T10:30:00Z │    12 │
│ xyz98765 │ refactor database      │ ~/myproject │ 2026-02-25T14:22:10Z │     7 │
└──────────┴────────────────────────┴─────────────┴──────────────────────┴───────┘
```

### Resume a session

```bash
rune --resume abc12345
```

Loads the session (including all messages) and continues the conversation from where it left off. Works with both `--prompt` and interactive TUI mode:

```bash
# Resume and send a follow-up prompt non-interactively
rune --resume abc12345 -p "now add error handling"

# Resume and continue interactively
rune --resume abc12345
```

Exits with code 1 if the session ID is not found.

### Show session tree

```bash
rune --show-tree abc12345
```

Renders the full subagent tree rooted at the given session using Rich's `Tree` widget:

```
Session Tree: abc12345
└── abc12345  implement auth feature  ~/myproject  turns=12
    ├── def67890  write JWT middleware  ~/myproject  turns=8
    └── ghi11223  write auth tests  ~/myproject  turns=5
        └── jkl44556  fix failing test  ~/myproject  turns=3
```

Exits with code 1 if the session ID is not found.

---

## Python API

### `SessionStore`

```python
from rune import SessionStore

store = SessionStore()                          # uses ~/.rune/sessions.db
store = SessionStore(db_path="/custom/path.db") # custom location
```

| Method | Description |
|--------|-------------|
| `save_session(session)` | Upsert session row + replace all messages |
| `load_session(session_id) -> Session` | Load by ID; raises `KeyError` if missing |
| `list_sessions(limit=20) -> list[dict]` | Recent sessions ordered by `updated_at DESC` |
| `get_session_tree(root_id) -> list[dict]` | Full subtree, flat list ordered by depth |
| `delete_session(session_id)` | Delete session and all descendants recursively |
| `close()` | Close the DB connection |

`delete_session` performs a recursive delete — all child sessions (and their messages) are removed before the parent to satisfy the foreign key constraint.

### Accessing the store from an agent

```python
from rune import Agent, AgentConfig

agent = Agent()

# The store is available directly
agent.store.list_sessions()

# Save the current session explicitly
agent.store.save_session(agent.session)

# Load and inspect a session tree
tree = agent.store.get_session_tree(agent.session.session_id)
for node in tree:
    print(f"{'  ' * node['depth']}{node['session_id']}  {node['title']}")
```

### Resuming a session

```python
agent = Agent()
agent.resume_session("abc12345")   # replaces agent.session in-place
result = agent.run("continue from where we left off")
```

Raises `KeyError` if the session ID is not found. Raises `RuntimeError` if `use_store=False`.

### Manual JSON persistence (legacy)

The original file-based persistence methods are still available on `Session` directly and are unaffected by the SQLite layer:

```python
session = agent.get_session()
session.save("backup.json")         # write to JSON file
session = Session.load("backup.json")  # load from JSON file
```

---

## Session Lifecycle

```
Agent.__init__()
    └── Session created (session_id assigned)
    └── store.save_session()          ← registered immediately

Agent.stream(user_input)
    └── session.add_user_message()
    └── [model call + tool calls loop]
        └── store.save_session()      ← after every TurnResult yield

Agent.shutdown()
    └── store.save_session()          ← final save
    └── store.close()
```

For subagents spawned via the `task` tool:

```
Agent._spawn_subagent()
    └── session.fork()                ← child.parent_session_id = parent.session_id
    └── child_agent = Agent(_store=self.store)
        └── store.save_session(child) ← registered immediately (with parent link)
    └── child_agent.run(prompt)
        └── store.save_session()      ← after every turn (shared store)
    └── store.save_session(child)     ← final save after run completes
```

---

## Compaction

When a session grows beyond 100 messages (`session.needs_compaction()`), the agent automatically compacts it:

1. The model is asked to summarize the conversation so far.
2. All but the last 10 messages are replaced with a `[CONVERSATION SUMMARY]` system message.
3. AGENTS.md content is stripped from the preserved system prompt (it will be re-injected fresh on the next turn).

The compacted session is saved to the DB after compaction. The full original message history is not retained in the DB — only the compacted form.
