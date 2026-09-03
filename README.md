# claude-handoff-skill

A [Claude Code](https://claude.com/claude-code) skill that writes a **handoff summary** before you close the current session, so a brand-new session — with zero memory of this one — can pick up exactly where you left off.

## Why

Long Claude Code sessions eventually hit context limits, or you just want to start a clean window. Re-explaining what's done, what's next, and *why* you made certain calls wastes time and things get lost. This skill makes Claude gather real evidence (`git status`, `git diff`, `git log`) instead of relying on its memory of the conversation, then writes a compact, structured summary you can hand to the next session.

## What it produces

Four fixed sections, in the language you've been using in the conversation:

1. **Completed work** — what was done, which files were touched, with uncommitted / committed-but-unpushed / stashed changes called out separately
2. **Next steps** — ordered by priority, each one a concrete action (which file, which command) — never something vague like "keep optimizing"
3. **Technical decisions & caveats** — only what a new session *can't* infer from reading the code: why A over B, ruled-out approaches, constraints, files not to touch
4. **Suggested first prompt** — a copy-pasteable block with the project path, current branch, and the first thing to do, ready to paste into the new session

Kept to one page. It's a handoff, not a report — the new session can read the code for anything not worth repeating here.

### Example output

```
## 1. Completed work
- Added rate limiting to the login endpoint → `src/auth/rateLimiter.ts` (new), `src/auth/login.ts`
- Uncommitted: `src/auth/rateLimiter.ts` has a TODO for the Redis key TTL
- Committed but not pushed: `a3f9c1e fix: correct off-by-one in retry backoff` (1 commit ahead of origin/main)

## 2. Next Steps
1. Decide the Redis key TTL in `src/auth/rateLimiter.ts:42` (currently hardcoded to 60s, marked TODO)
2. Run `npm test src/auth` to confirm the new rate-limit tests pass
3. Push the pending commit once TTL is settled

## 3. Technical decisions & caveats
- Chose a sliding-window counter over a fixed-window one because the fixed-window
  version let bursts double at window boundaries — see discussion in this session.
- Do not touch `src/auth/legacyLogin.ts` — it's kept only for an in-flight migration
  and is scheduled for deletion in a separate ticket.

## 4. Suggested first prompt
​```
Project: ~/code/my-app, branch: feature/rate-limit
Continue from src/auth/rateLimiter.ts:42 — decide the Redis key TTL for the
login rate limiter and finish the TODO there.
​```
```

## Installation

Claude Code loads skills from `~/.claude/skills/`. Clone this repo anywhere and symlink (or copy) the `handoff/` directory in:

```bash
git clone https://github.com/heartwar9420/claude-handoff-skill.git
mkdir -p ~/.claude/skills
ln -sfn "$(pwd)/claude-handoff-skill/handoff" ~/.claude/skills/handoff
```

A symlink keeps you on the latest version with a simple `git pull`; a plain `cp -r` works too if you'd rather vendor a copy.

Restart Claude Code (or start a new session) and the skill is available.

## Usage

Just ask, in your own words — the skill triggers on natural phrasing like:

- "give me a handoff summary" / "write a handoff"
- "I'm about to run out of context"
- "summarize where we are so I can continue in a new chat"
- 交接、交接摘要、換視窗、開新對話、上下文快要滿了、幫我總結目前進度

It also takes an optional file path argument (e.g. `/handoff HANDOFF.md`) to save the summary to a file in addition to printing it in the chat — handy if you want it to survive the window closing without copy-pasting.

## How it works

Before writing anything, the skill runs:

```
git status --short --branch
git diff --stat HEAD
git log --oneline -10
git stash list
```

Every file path in the output must trace back to that evidence or to files this session actually touched — anything else gets flagged as unverified rather than stated as fact. Outside a git repo, the whole "Completed work" section is flagged as unverified, since there's nothing to cross-check it against.

## License

[MIT](LICENSE)

---

## 繁體中文說明

這是一支 [Claude Code](https://claude.com/claude-code) skill，在你要關掉目前視窗前產出一份「交接摘要」，讓完全沒有本視窗記憶的新 session 可以直接接手。

**做法**：動筆前先跑 `git status --short --branch`、`git diff --stat HEAD`、`git log --oneline -10`、`git stash list` 蒐證，不靠對話記憶猜路徑；非上述來源的內容一律標記為推測。

**輸出四段**：已完成進度（含未提交／已提交未推送／stash 分開講）、Next Steps（每項是可執行的具體動作）、技術決策與注意事項（只寫程式碼看不出來的東西）、建議的第一句 Prompt（可直接複製貼上）。

**安裝**：clone 這個 repo 後，把 `handoff/` 目錄 symlink 或複製進 `~/.claude/skills/handoff`，重開 Claude Code 就會生效。

**觸發**：直接用自然語言講「交接」「換視窗」「上下文快滿了」「幫我總結目前進度」即可，也可以帶檔案路徑參數（如 `/handoff HANDOFF.md`）額外存成檔案。
