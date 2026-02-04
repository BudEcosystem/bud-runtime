# Daily Memory Folder

This folder contains day-to-day learnings. Files older than 30 days are archived to `archive/`.

## File Naming

| Pattern | Example |
|---------|---------|
| `YYYY-MM-DD.md` | `2025-02-04.md` |

## Entry Format

```markdown
## [HH:MM] Title

**Category**: correction | pattern | preference | architecture | convention
**Service**: budapp | budadmin | budcluster | budsim | budgateway | budmodel | budmetrics | budnotify | ask-bud | budeval | budplayground | budCustomer | general
**Tags**: tag1, tag2

> The learning content in one or two sentences.

---
```

## Commands

- `/budmem add <content>` - Add a learning (auto-detects metadata)
- `/budmem search <query>` - Search across all memory
- `/budmem promote` - Move learnings to long-term memory
- `/budmem clean` - Archive files older than 30 days
