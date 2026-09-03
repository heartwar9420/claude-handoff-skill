---
name: handoff
description: 產出交接摘要（Handoff Summary），供使用者關閉目前視窗、在新對話視窗延續開發。Produces a handoff summary so the user can close the current window and resume in a new session with zero memory of it. 觸發詞：交接、交接摘要、handoff、換視窗、開新視窗、開新對話、接手、上下文快要滿了、幫我總結目前進度、繼續後續開發 / Trigger words: handoff, context handoff, session summary, hand off to a new chat, continue in a new session, context window almost full. 輸出四段：已完成進度與檔案路徑、Next Steps、技術決策與注意事項、建議的第一句 Prompt。
license: MIT
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git stash list:*)
argument-hint: "[output-file-path]"
metadata:
  tags: "handoff, context, session, summary"
  category: "productivity"
---

# handoff

產出一份能讓「完全沒有本視窗記憶」的新 session 直接接手的摘要。
Produces a summary that lets a brand-new session, with zero memory of this window, pick up the work directly.

## 先蒐證，再下筆（必做）／Gather evidence first, then write (mandatory)

動筆前一定先執行，不要憑對話印象寫路徑。
Always run these before writing — never rely on memory of the conversation for paths or state.

```
git status --short --branch
git diff --stat HEAD
git log --oneline -10
git stash list
```

- 檔案路徑一律用**專案根目錄的相對路徑**，且必須來自上面的輸出或本 session 實際讀寫過的檔案。
  File paths must be relative to the project root, and must come from the output above or from files this session actually read/wrote.
- 非上述來源的事項，標記 `(推測)` / `(unverified)`。寧可標推測，不可寫得像已驗證。
  Anything not sourced this way must be flagged as unverified — prefer flagging over writing it as if confirmed.
- 不在 git repo 就跳過上面的指令，改用本 session 實際碰過的絕對路徑，並把「已完成進度」整段標記為 `(推測)`——因為沒有 git 可以交叉比對。
  Not in a git repo → skip the commands above, use absolute paths this session actually touched, and flag the entire "Completed work" section as unverified, since none of it could be cross-checked against git.
- `git stash list` 有內容的話，把 stash 裡的未提交工作獨立列一條，不要跟工作區的未提交變更混在一起。
  If `git stash list` returns entries, list stashed work as its own line, separate from working-tree uncommitted changes.

## 輸出語言／Output language

跟隨對話目前使用的語言。段落標題與結構不因語言而變。
Match the language the user has been using in this conversation. Keep section headers and structure identical regardless of language.

## 輸出格式（固定四段）／Output format (four fixed sections)

### 1. 已完成進度 / Completed work
逐項條列「做了什麼 → 動到哪些檔案」，檔案路徑用行內程式碼。
未提交 / 已提交未推送 / stash 裡的變更要分開講清楚（分支與 ahead/behind 狀態來自 `git status --short --branch` 第一行）。

Bullet list of "what was done → which files were touched", file paths in inline code.
Separate uncommitted changes, committed-but-unpushed changes, and stashed changes (branch and ahead/behind status comes from the first line of `git status --short --branch`).

### 2. Next Steps
依優先序排列，每項寫明**下一步的具體動作**（要改哪個檔案、要跑哪個指令），
不要寫「繼續優化」這種無法執行的句子。已知卡住的點要寫出卡在哪。

Ordered by priority. Each item states the concrete next action (which file to edit, which command to run) — never something unexecutable like "keep optimizing." Note where any known blocker sits.

### 3. 技術決策與注意事項 / Technical decisions & caveats
只寫**新視窗看程式碼也看不出來的東西**：為什麼選 A 不選 B、已排除的方案與原因、
命名規範、環境／金鑰限制、不能碰的檔案。
程式碼本身已經寫明的結構不要重複。

Only what a new window can't infer by reading the code: why A was chosen over B, options already ruled out and why, naming conventions, environment/credential constraints, files that must not be touched. Don't repeat structure the code already makes obvious.

### 4. 建議的第一句 Prompt / Suggested first prompt
一段可直接複製貼上的文字，內含：專案路徑、當前分支、要接續的第一件事。
放在獨立的程式碼區塊裡。

A copy-pasteable block containing: project path, current branch, and the first thing to pick up. Put it in its own code block.

## 篇幅／Length

全長控制在一頁內。這是交接，不是報告；寫不完的細節留給新視窗自己讀程式碼。
Keep the whole thing to one page. This is a handoff, not a report — leave detail for the new window to get by reading the code itself.

## 選用：存成檔案／Optional: save to a file

如果呼叫時帶了路徑參數（`$ARGUMENTS`），除了輸出到對話框外，也把摘要寫進該檔案，這樣關掉視窗後內容還在。
沒帶參數時只輸出到對話框，不主動寫進使用者的專案。

If invoked with a path argument (`$ARGUMENTS`), also write the summary to that file in addition to printing it in the chat, so it survives closing the window. Without an argument, only print it in the chat — don't write into the user's project uninvited.
