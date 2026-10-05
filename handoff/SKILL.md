---
name: handoff
description: 產出交接摘要（Handoff Summary）或接續上一棒進度。供使用者關閉目前視窗、在新對話視窗延續開發。Produces or resumes a handoff summary so you can switch sessions cleanly without memory loss. 觸發詞：交接、交接摘要、handoff、換視窗、開新視窗、開新對話、上下文快要滿了、幫我總結目前進度 / Trigger words: handoff, resume, resume handoff, context handoff, session summary, continue in a new session, context window almost full. 支援產出四段式交接檔並自動登錄 Obsidian 待辦清單，接續則僅由 `/handoff resume` 明確觸發。
license: MIT
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git stash list:*), Bash(python3 *handoff-manager.py*)
argument-hint: "[resume <issue|branch> | list | complete | output-file-path]"
metadata:
  tags: "handoff, context, session, summary, resume, todo"
  category: "productivity"
---

# handoff

產出一份能讓「完全沒有本視窗記憶」的新 session 直接接手的摘要，或在新視窗接續上一棒的開發進度。

---

## 兩條核心運作路徑

1. **產出交接（Handoff 模式）**：使用者說「交接」「換視窗」「上下文快滿了」「總結進度」或輸入 `/handoff` 時執行。
2. **接續交接（Resume 模式）**：僅在使用者輸入 `/handoff resume` 時執行（不以自然語句觸發）。

---

## 模式一：產出交接（Handoff）

### 1. 先蒐證，再下筆（必做）
動筆前一定先執行，不要憑對話印象寫路徑：
```bash
git status --short --branch
git diff --stat HEAD
git log --oneline -10
git stash list
```

- 檔案路徑一律用**專案根目錄的相對路徑**，且必須來自上面的輸出或本 session 實際讀寫過的檔案。
- 非上述來源的事項，標記 `(推測)` / `(unverified)`。寧可標推測，不可寫得像已驗證。
- 不在 git repo 就跳過上面的指令，改用本 session 實際碰過的絕對路徑，並把「已完成進度」整段標記為 `(推測)`。
- `git stash list` 有內容的話，把 stash 裡的未提交工作獨立列一條。

### 2. 內部組織四段式交接內容（存檔用）
在記憶體中整理出完整的四段式架構：
1. **已完成進度**：逐項條列「做了什麼 → 動到哪些檔案（相對路徑）」，分開已提交 / 未提交 / stash。
2. **Next Steps**：依優先序排列，每項必須是具體可執行的動作（哪個檔案、什麼指令），註明 blocker。
3. **技術決策與注意事項**：只寫程式碼看不出來的事情（架構選擇、限制、不能動的檔案），**必寫「已探索但放棄的路徑（踩坑紀錄）」**。
4. **建議的第一句 Prompt**：包含專案路徑、當前分支、要接續的第一件事。

### 3. 自動存檔與 Obsidian 待辦登記（必做）
將上述四段內容寫入臨時檔案（如 `/tmp/current-handoff.md`），調用腳本存檔：
```bash
python3 "$HOME/.claude/skills/handoff/scripts/handoff-manager.py" record /tmp/current-handoff.md
```
- **專案與分支隔離**：自動存入 `~/.claude/handoffs/${REPO}__${BRANCH}.md`，多專案/多分支絕不互相覆蓋。
- **Obsidian 待辦清單**：若使用者本機存在 `~/Documents/obsidian-vault/Todo/待辦清單.md`，腳本會依 vault 既有 schema 在 `Todo/未完成/` 建立一份對應筆記（`title`/`done_date`/`skills`/`impact`/`issue_link`/`pr_link`/`star` frontmatter，body 含完整四段式交接內容），並在待辦清單頂端插入一行**連結**該筆記的 checkbox：
  `- [ ] [[issue -<num> handoff|issue #<num> handoff (<next-step-summary>)]]`
  （筆記檔名把 `#` 換成 `-`，因為 `#` 在 `[[wiki-link]]` 裡會被解讀成標題錨點，這點跟 vault 裡其他手動建的筆記檔名慣例一致。）純文字、沒有連結目標的行在 Obsidian 裡點不開，因此這裡務必是連結而非純文字。讓使用者在手機或 Obsidian 一眼就能掌握有哪些任務換手中，並點進去看完整內容。
- 若使用者調用時帶有指定路徑參數（`$ARGUMENTS`），額外複製一份至該路徑。
- 存檔完成後清理臨時檔（`rm -f /tmp/current-handoff.md`）。

### 4. 對話框極簡回報（省 Token 原則）
> [!IMPORTANT]
> **不要在對話框中印出冗長的四段式交接內容！**
> 因為內容已完整存檔至本機與 Obsidian，使用者即將關閉視窗，印出長篇大論純粹浪費輸出 Token。
> 對話框**只輸出極簡回報**（4 行以內）：

```text
已完成交接存檔與 Obsidian 待辦登記！
• 交接檔案：~/.claude/handoffs/<repo>__<branch>.md
• 下一步驟：<Next Step 1 一句話>
• Obsidian：已新增至待辦清單
```

> 不要附「新視窗輸入『繼續 issue #<num>』即可接手」這類提示；使用者習慣直接貼交接檔路徑給新 agent。

---

## 模式二：接續上一棒（Resume）

當使用者輸入 `/handoff resume [query]` 時：

1. **讀取交接內容**：
   執行腳本取得對應交接檔案：
   ```bash
   python3 "$HOME/.claude/skills/handoff/scripts/handoff-manager.py" resume [query]
   ```
   （若沒帶參數，腳本會自動依當前專案與分支智慧尋找）。

2. **主動回報並接續**：
   - 以繁體中文向使用者回報：「已為您載入 issue #xxx 的交接紀錄。」
   - 簡潔摘要：目前已完成項目、已排除的踩坑方案、以及 **Next Steps 的第一個具體動作**。
   - 詢問使用者是否直接開始執行，或有其他指示。

---

## 模式二之一：接手自動打勾（Claim，由 hook 觸發）

使用者把交接檔路徑、交接檔內容或 Obsidian 筆記名（`issue -<num> handoff`）貼給新 agent 時，`UserPromptSubmit` hook 會自動執行：
```bash
python3 "$HOME/.claude/skills/handoff/scripts/handoff-manager.py" hook-claim
```
- 補上筆記 `done_date`、移除待辦清單那行，交給 `auto-move-done` 搬進 `Todo/已完成/<日期>/`。
- **不刪 `~/.claude/handoffs/` 的交接檔**，新 session 當掉時還能重貼；刪檔留給模式三的 `complete`。
- 手動補跑：`handoff-manager.py claim [issue|branch]`。重複執行無副作用。
- 看到 hook 輸出 `[handoff claim] ...` 代表已自動處理，不要再手動 complete。

---

## 模式三：任務完成清理（Complete）

當該交接任務實作完成並開啟 PR（`gh pr create`）或使用者明確指示「完成了」時：
```bash
python3 "$HOME/.claude/skills/handoff/scripts/handoff-manager.py" complete [query]
```
- 自動清理 `~/.claude/handoffs/` 對應的交接檔案。
- 幫對應的 Obsidian 筆記補上 `done_date`，並把 `Todo/待辦清單.md` 裡連到它的那行整行移除——交給 vault 既有的 `auto-move-done` 外掛依 `done_date` 自動把筆記搬進 `Todo/已完成/<日期>/`，跟其他任務走同一套歸檔機制，不再是留一個打勾但點不開的純文字行。
