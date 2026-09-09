# claude-handoff-skill

A [Claude Code](https://claude.com/claude-code) skill that writes a **handoff summary** before you close the current session, and lets a brand-new session — with zero memory of this one — pick up exactly where you left off.

## Why

Long Claude Code sessions eventually hit context limits, or you just want to start a clean window. Re-explaining what's done, what's next, and *why* you made certain calls wastes time and things get lost. This skill makes Claude gather real evidence (`git status`, `git diff`, `git log`) instead of relying on its memory of the conversation, writes a compact, structured summary, saves it locally, and supports one-command resuming in your next session.

## What it produces

Four fixed sections, in the language you've been using in the conversation:

1. **Completed work** — what was done, which files were touched, with uncommitted / committed-but-unpushed / stashed changes called out separately
2. **Next steps** — ordered by priority, each one a concrete action (which file, which command) — never something vague like "keep optimizing"
3. **Technical decisions & caveats** — only what a new session *can't* infer from reading the code: why A over B, ruled-out approaches, constraints, files not to touch
4. **Suggested first prompt** — a copy-pasteable block with the project path, current branch, and the first thing to do

Kept to one page. It's a handoff, not a report — the new session can read the code for anything not worth repeating here.

## Features

- **Automated Local Storage**: Automatically saves handoffs to `~/.claude/handoffs/${REPO}__${BRANCH}.md` so concurrent sessions and git worktrees never collide.
- **Obsidian Todo Integration**: If an Obsidian vault is detected at `~/Documents/obsidian-vault`, it automatically registers an uncompleted task `- [ ] issue #<num> handoff (<next-step>)` into `Todo/待辦清單.md`.
- **Seamless Resume**: In your new session, just say `繼續 issue #<num>` or `/handoff resume` to load the exact handoff without wasting startup tokens.
- **Auto Clean-up**: Run `/handoff complete` or let your PR hook mark the task `- [x]` and clean up the handoff file.

## Installation

Claude Code loads skills from `~/.claude/skills/`. Clone this repo anywhere and symlink (or copy) the `handoff/` directory in:

```bash
git clone https://github.com/heartwar9420/claude-handoff-skill.git
mkdir -p ~/.claude/skills
ln -sfn "$(pwd)/claude-handoff-skill/handoff" ~/.claude/skills/handoff
```

Restart Claude Code (or start a new session) and the skill is available.

## Usage

### 1. Generating a handoff
Just ask in your own words:
- "give me a handoff summary" / "write a handoff"
- "I'm about to run out of context"
- "summarize where we are so I can continue in a new chat"
- 交接、交接摘要、換視窗、開新對話、上下文快要滿了、幫我總結目前進度

### 2. Resuming in a new session
In a fresh window, tell Claude:
- `繼續 issue #1272`
- `接手 issue #1272`
- `/handoff resume`

Claude will retrieve the saved handoff, report the status and next step, and proceed.

### 3. Completing & Cleaning up
- When PR is created or work is done: `/handoff complete` (or automated via git hooks)

## License

[MIT](LICENSE)

---

## 繁體中文說明

這是一支 [Claude Code](https://claude.com/claude-code) skill，在你要關掉目前視窗前產出一份「交接摘要」，並支援在新視窗精準接手。

- **自動存檔**：自動存至 `~/.claude/handoffs/${REPO}__${BRANCH}.md`，多專案/多分支並行絕不衝突。
- **Obsidian Todo 連動**：自動在 `~/Documents/obsidian-vault/Todo/待辦清單.md` 加上 `- [ ] issue #<num> handoff (<下一步>)`，手機/電腦一目了然。
- **極簡接手（省 Token）**：在新視窗只要說「`繼續 issue #<num>`」或 `/handoff resume`，Agent 就會讀檔接手，不主動浪費開機 Token。
- **完工清理**：開 PR 或輸入 `/handoff complete` 自動打勾 `- [x]` 並刪除交接檔。
