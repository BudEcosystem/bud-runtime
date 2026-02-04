---
name: budmem
description: Memory management - persistent learnings across sessions
---

# budmem - Memory System

Handle memory operations based on the command in `$ARGUMENTS`:

## Command Routing

Parse `$ARGUMENTS` and execute:

| If starts with | Action |
|----------------|--------|
| (empty) | Show status - list recent learnings |
| `add <content>` | Add learning to today's file |
| `search <query>` | Search across all memory files |
| `promote` | Move learnings to long-term memory |
| `flush` | Save session learnings before context loss |
| `clean` | Archive files older than 30 days |

---

## Session Initialization

**At session start, automatically:**
1. Read `MEMORY.md` to load long-term context
2. Scan `memory/` for files from the last 7 days
3. Keep recent learnings in context for duplicate detection

---

## Command: (empty) - Show Status

Display memory status and recent learnings.

**Steps:**
1. Read `MEMORY.md` and summarize content
2. List files in `memory/` sorted by date (newest first)
3. Show last 5 learnings from most recent files

---

## Command: add <content>

Add a new learning to today's file.

**Steps:**
1. Extract content from `$ARGUMENTS` (everything after "add ")
2. **Check for duplicates** - search existing memories for similar content
3. If duplicate found, show it and ask user to confirm
4. Auto-detect metadata from content and conversation context
5. Append to `memory/YYYY-MM-DD.md` using entry format below
6. Confirm with one-line summary

**Auto-detected metadata:**
- **Category**: correction | pattern | preference | architecture | convention
- **Service**: budapp | budadmin | budcluster | budsim | budgateway | general
- **Tags**: Extract key terms from content

---

## Command: search <query>

Search across all memory files.

**Steps:**
1. Extract query from `$ARGUMENTS` (everything after "search ")
2. Search `MEMORY.md` for matches
3. Search all files in `memory/` folder
4. Display matches with file location and context

---

## Command: promote

Move learnings from daily files to MEMORY.md.

**Steps:**
1. List recent learnings from `memory/` files (last 7 days)
2. Ask user which to promote (number or content)
3. Append to `MEMORY.md` under appropriate section
4. Mark as promoted in source file with `[PROMOTED]` tag

---

## Command: flush

Save current session learnings before context is lost.

**Steps:**
1. Review conversation for corrections, preferences, patterns
2. Check each against existing memories for duplicates
3. Present list and ask user to confirm each
4. Write confirmed learnings to today's file
5. Suggest any that should be promoted to MEMORY.md

---

## Command: clean

Archive daily files older than 30 days.

**Steps:**
1. Create `memory/archive/` if needed
2. Move files older than 30 days to archive
3. Report: "Archived X files from [date range]"

---

## Entry Format

```markdown
## [HH:MM] Title

**Category**: correction | pattern | preference | architecture | convention
**Service**: budapp | budadmin | budcluster | budsim | budgateway | general
**Tags**: tag1, tag2

> The learning content in one or two sentences.

---
```

---

## Auto-Learn Triggers

Detect these patterns in user messages and offer to save:

| Pattern | Example | Action |
|---------|---------|--------|
| `remember:` | "remember: always use X" | Save immediately |
| `important:` | "important: never do Y" | Save immediately |
| `no, use X` | "no, use raw SQL" | Prompt to save |
| `actually` | "actually, I meant..." | Prompt to save |
| `don't use` | "don't use query builders" | Prompt to save |
| `prefer X` | "I prefer Zustand" | Prompt to save |
| `always X` | "always add error handling" | Prompt to save |
| `never X` | "never commit .env" | Prompt to save |

---

## Hooks (Optional)

Add to `.claude/settings.json` for automatic reminders:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'BUDMEM: Context compacting. Run /budmem flush to save learnings.'"
          }
        ]
      }
    ]
  }
}
```

---

## File Structure

```
.claude/skills/budmem/
├── SKILL.md              # This file
├── MEMORY.md             # Long-term curated knowledge
└── memory/
    ├── YYYY-MM-DD.md     # Daily logs
    └── archive/          # Old files (30+ days)
```

---

## MEMORY.md Sections

```markdown
# Long-term Memory

## Architecture Decisions
## Coding Preferences
## Project Conventions
## Service-Specific
### budapp
### budadmin
### budcluster
### budsim
### budgateway
## Anti-patterns
```

---

## Examples

**Add a learning:**
```
/budmem add Always use structlog for logging in Python services
> Checking duplicates... none found.
> Added to memory/2025-02-04.md (category: convention, service: general)
```

**Search:**
```
/budmem search logging
> Found 2 matches:
> - memory/2025-02-04.md: "Always use structlog for logging..."
> - MEMORY.md: "All services use structlog with JSON output"
```

**Duplicate detection:**
```
/budmem add Use structlog for logging
> Similar learning exists in memory/2025-02-04.md:
> "Always use structlog for logging in Python services"
> Still add? (y/n)
```
