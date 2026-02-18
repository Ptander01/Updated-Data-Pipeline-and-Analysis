# Session Handoff Template

**Purpose:** Consistent format for resuming work across chat sessions within a workstream.

---

## Instructions

1. Copy this template at the END of each session
2. Fill in the sections below
3. Save as `SESSION_HANDOFF_{WORKSTREAM}_{DATE}.md` in `00_docs/progress/`
4. Reference in `WORKFLOW_WIP_TRACKER.md` for cross-workstream visibility

---

# Session Handoff — {Workstream Name}

**Chat Started:** {date}
**Last Session:** Session {N} on {date}
**Workstream:** {New Sources | UCID Design | Dashboard}

---

## 📍 Where We Left Off

### Completed This Session

1. {Completed item 1}
2. {Completed item 2}
3. {Completed item 3}

### In Progress (Not Complete)

1. {Item with current status — e.g., "Script created but not tested"}
2. {Item with partial progress — e.g., "Schema analysis 70% complete"}

### Blocked/Waiting

1. {Item} — waiting on {reason}
2. {Item} — blocked by {external dependency}

---

## 🎯 Next Session Priorities

1. [ ] **Immediate:** {Most important next step}
2. [ ] **Follow-up:** {Secondary priority}
3. [ ] **Nice-to-have:** {If time permits}

---

## 📋 Key Decisions Made

| Decision | Rationale | Reversible? |
|----------|-----------|-------------|
| {Decision made} | {Why this choice} | Yes / No |
| {Decision made} | {Why this choice} | Yes / No |

---

## ⚠️ Impacts Other Workstreams

| Change Made | Affects | Update Required |
|-------------|---------|-----------------|
| {Change description} | {Workstream name} | {Document to update} |
| {Schema change} | {Pipeline, Dashboard} | {config.py, README} |

---

## 🔗 Related Context

### Files Created/Modified This Session

| File | Action | Purpose |
|------|--------|---------|
| {filepath} | Created | {brief description} |
| {filepath} | Modified | {what changed} |

### Scripts to Run Next

```python
# Step 1: {description}
exec(open(r"C:\...\scripts\{path}\{script}.py", encoding='utf-8').read())

# Step 2: {description}
exec(open(r"C:\...\scripts\{path}\{script}.py", encoding='utf-8').read())
```

### Key Documentation References

- `AI_CONTEXT_PROMPT.md` — Master project context
- `WORKFLOW_WIP_TRACKER.md` — Cross-workstream status
- `{relevant_doc.md}` — {why relevant}

---

## 📝 Resume Prompt

Copy this to start next session:

> I'm resuming work on **{workstream name}**.
>
> Last session (Session {N}, {date}) we completed:
> - {main accomplishment 1}
> - {main accomplishment 2}
>
> We were working on **{current focus}** and encountered **{any blockers}**.
>
> Current priority is **{next action}**.
>
> Please read `WORKFLOW_WIP_TRACKER.md` for full cross-workstream context.

---

## 📅 Session Timeline

| Time | Activity |
|------|----------|
| Start | Read context, reviewed tracker |
| +30m | {First major activity} |
| +1h | {Second major activity} |
| +2h | {Wrap-up, documentation} |
| End | Created handoff, updated tracker |

---

*Template version: 1.0 — February 11, 2026*
