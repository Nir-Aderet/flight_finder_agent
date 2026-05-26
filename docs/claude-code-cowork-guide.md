# Using Claude Code alongside Cowork — Practical Guide

This guide explains how to move between the **Cowork desktop app** and
**Claude Code** (the terminal CLI) on the same project, and when to use each.

---

## 1. What each tool is good at

| Task | Best tool |
|---|---|
| Planning, architecture, doc generation | Cowork |
| Writing or editing many files at once | Cowork |
| Browsing the web for research | Cowork |
| Asking "what should I build next?" | Cowork |
| Running code, installing deps, running tests | **Claude Code** |
| Iterative refactoring inside a file | **Claude Code** |
| Debugging a failing test | **Claude Code** |
| Git operations (commit, branch, diff) | **Claude Code** |
| Long coding sessions with many file edits | **Claude Code** |

The two tools share the same project folder on disk — changes made in one are
immediately visible in the other.

---

## 2. One-time setup: install Claude Code

```bash
# Requires Node.js 18+ (check: node --version)
npm install -g @anthropic/claude-code
```

Verify:
```bash
claude --version
```

If `npm` isn't installed, get Node.js from https://nodejs.org (LTS version).

---

## 3. Switching to Claude Code for your project

### Step 1 — Open a terminal in your project folder

```bash
cd "C:\Users\Nir\Documents\Claude\Projects\flight finder agent"
```

Or open the folder in VS Code and use the integrated terminal.

### Step 2 — Start Claude Code

```bash
claude
```

Claude Code reads `CLAUDE.md` automatically on startup — this gives it full
context about the project without you having to re-explain anything.

### Step 3 — Give it a task

Claude Code works best with direct, specific instructions:

```
implement M2: create all 5 pydantic model files per docs/03_repo_structure.md
and their unit tests in tests/unit/models/
```

or:

```
run pytest -q and fix any failures
```

### Step 4 — Review changes

Claude Code shows a diff of every file it touches before writing. Review and
approve (or reject) each change.

---

## 4. Keeping context in sync between Cowork and Claude Code

The key file is **`CLAUDE.md`** in the project root. It is the shared memory
between both tools.

**Rule:** whenever Cowork finishes a meaningful chunk of work (a milestone, a
design decision, a new module), update `CLAUDE.md` to reflect the new state.
Then Claude Code will start the next session already knowing what's done.

**What belongs in CLAUDE.md:**
- Current phase / milestone status (what's done, what's next)
- Locked decisions (models, libraries, naming conventions)
- How to run tests / lint / the CLI
- Where to find key context (which doc answers which question)

**What does NOT belong in CLAUDE.md:**
- Full file contents (link to the file instead)
- Step-by-step history of what was built (that's `git log`)
- Anything that changes every session

---

## 5. Recommended workflow per milestone

```
Cowork                              Claude Code
──────                              ───────────
Plan the milestone
Write / update design docs
Update CLAUDE.md with new state
                              ──►   claude
                                    (reads CLAUDE.md)
                                    Implement the milestone
                                    Run tests, fix failures
                                    git add . && git commit -m "feat(mN): ..."
Come back to Cowork
Review output, update TODO.md
Plan the next milestone
```

---

## 6. Useful Claude Code slash commands

| Command | What it does |
|---|---|
| `/help` | List all available commands |
| `/init` | Generate a CLAUDE.md from the current codebase (first-time setup) |
| `/review` | Review the current branch's changes as a pull request |
| `/clear` | Clear conversation history (keeps file changes) |
| `Ctrl+C` | Cancel the current operation |
| `Ctrl+R` | Search conversation history |

---

## 7. Tips for good results in Claude Code

**Be specific about scope.** "implement models/query.py per the spec in
docs/03_design.md §4.1" is better than "implement the models".

**Reference existing files.** "Follow the same pattern as models/query.py" saves
a lot of back-and-forth.

**Ask it to run tests after each change.** Claude Code can run `pytest` and fix
failures in the same session.

**Use `/clear` between unrelated tasks.** A fresh context window is faster and
less error-prone than a 50-message history.

**Commit often.** Tell Claude Code to commit after each logical unit of work.
Small commits are easier to review and revert.

---

## 8. When to come back to Cowork

- You need to search the web or read documentation
- You want to discuss a design decision before coding it
- You need to create a document, presentation, or report
- You want a high-level review of multiple files at once
- You're planning the next phase or milestone

---

## 9. Quick reference for this project

```bash
# Start Claude Code in the project
cd "C:\Users\Nir\Documents\Claude\Projects\flight finder agent"
claude

# Example prompts to paste on startup:
# "Read CLAUDE.md and TODO.md, then implement the next pending milestone."
# "Run pytest -q and fix any failing tests."
# "Implement M2: all 5 model files + unit tests per docs/03_repo_structure.md."
```
