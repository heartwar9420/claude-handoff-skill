#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handoff Manager for Claude Code.
Handles recording, resuming, listing, and completing handoff summaries,
with seamless integration into Obsidian Todo/待辦清單.md.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_VAULT = Path.home() / "Documents" / "obsidian-vault"
HANDOFF_DIR = Path.home() / ".claude" / "handoffs"


def yaml_quote(text):
    """Double-quote a string for use as a YAML frontmatter scalar value.

    An unquoted value containing ' #' (whitespace then hash) gets silently
    truncated by YAML parsers, which treat it as a comment start — e.g.
    'issue #1334 handoff (...)' parses down to just 'issue'. Obsidian's own
    frontmatter parser hits the same rule, so a bare title like that renders
    wrong forever, not just once. Quoting sidesteps this (and ':', etc.).
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def slugify_for_filename(text):
    """Make text safe as an Obsidian note filename.

    '#' is replaced with '-' (not stripped) because '#' inside a [[wiki-link]]
    is parsed by Obsidian as a heading reference, breaking the link. This
    mirrors the convention already used elsewhere in this vault, e.g. an item
    titled "...(#1289)" is filed as "...(-1289).md".
    """
    text = text.replace("#", "-")
    for ch in '/\\:*?"<>|':
        text = text.replace(ch, "")
    return text.strip()


def today_str():
    return datetime.date.today().isoformat()


def get_github_url(num):
    """Best-effort GitHub issue/PR URL lookup via gh CLI. Returns "" on any failure
    (gh not installed, not authenticated, offline, etc.) rather than raising."""
    if not num:
        return ""
    try:
        return (
            subprocess.check_output(
                ["gh", "issue", "view", str(num), "--json", "url", "-q", ".url"],
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return ""


def get_git_info():
    """Detect repo name and current branch from git."""
    try:
        top_level = (
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
        repo_name = os.path.basename(top_level)
    except Exception:
        repo_name = os.path.basename(os.getcwd())

    try:
        branch = (
            subprocess.check_output(
                ["git", "branch", "--show-current"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        branch = "unknown"

    if not branch:
        branch = "detached"

    return repo_name, branch


def extract_issue_num(branch, text=""):
    """Extract issue number from branch name or text."""
    # Check branch first: e.g. issue/1272, issue-1272, #1272
    m = re.search(r"(?:issue[/-]|#|^)([0-9]+)", branch)
    if m:
        return m.group(1)
    if text:
        m = re.search(r"#([0-9]+)", text)
        if m:
            return m.group(1)
    return None


def extract_summary_from_content(content):
    """Attempt to extract a short next step summary from handoff content."""
    # Look for Next Steps section
    next_steps_m = re.search(
        r"##\s*(?:2\.\s*)?(?:Next\s*Steps|下一步|Next\s*Step)[^\n]*\n(.*?)(?=\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if next_steps_m:
        steps_text = next_steps_m.group(1).strip()
        # Find first non-empty numbered item or bullet
        for line in steps_text.splitlines():
            line = line.strip()
            item_m = re.match(r"^(?:[0-9]+\.|\-|\*)\s*(.+)$", line)
            if item_m:
                summary = item_m.group(1).strip()
                # Clean up markdown formatting and limit length
                summary = re.sub(r"[`*_[\]]", "", summary)
                if len(summary) > 60:
                    summary = summary[:57] + "..."
                return summary

    # Fallback: check Suggested first prompt
    prompt_m = re.search(
        r"##\s*(?:4\.\s*)?(?:Suggested\s*first\s*prompt|建議的第一句\s*Prompt)[^\n]*\n.*?```(?:text)?\s*\n(.*?)\n```",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if prompt_m:
        lines = [l.strip() for l in prompt_m.group(1).strip().splitlines() if l.strip()]
        if lines:
            line = lines[-1]
            if len(line) > 60:
                line = line[:57] + "..."
            return line

    return "待接續開發"


def cmd_record(args):
    repo_name, branch = get_git_info()
    if args.repo:
        repo_name = args.repo
    if args.branch:
        branch = args.branch

    # Read content from file or stdin
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    if not content.strip():
        print("錯誤：交接內容為空。", file=sys.stderr)
        sys.exit(1)

    issue_num = args.issue or extract_issue_num(branch, content)
    summary = args.summary or extract_summary_from_content(content)

    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    branch_slug = branch.replace("/", "--").replace(" ", "-")
    target_path = HANDOFF_DIR / f"{repo_name}__{branch_slug}.md"
    target_path.write_text(content, encoding="utf-8")
    print(f"交接檔案已存檔：{target_path}")

    # Update Obsidian Todo/待辦清單.md if vault exists
    vault_path = Path(args.vault) if args.vault else DEFAULT_VAULT
    todo_file = vault_path / "Todo" / "待辦清單.md"

    if todo_file.exists():
        try:
            if issue_num:
                display_title = f"issue #{issue_num} handoff ({summary})"
                note_stem = slugify_for_filename(f"issue #{issue_num} handoff")
            else:
                display_title = f"{branch} handoff ({summary})"
                note_stem = slugify_for_filename(f"{branch} handoff")

            # Write a real linked note (matching the vault's Todo/未完成 schema) instead of
            # a bare-text checkbox line, otherwise the item has nothing to link to and can't
            # be opened from Obsidian.
            note_dir = vault_path / "Todo" / "未完成"
            note_dir.mkdir(parents=True, exist_ok=True)
            note_path = note_dir / f"{note_stem}.md"

            if not note_path.exists():
                # A note with this stem may already exist under Todo/已完成/<date>/ —
                # e.g. a past handoff for the same issue number was already completed
                # and moved out of Todo/未完成/. Reusing note_stem blindly would create
                # a second, colliding file that the vault's own auto-move-done plugin
                # can't relocate (destination name taken), leaving an orphan behind.
                done_matches = list((vault_path / "Todo" / "已完成").glob(f"**/{note_stem}.md"))
                if done_matches:
                    note_stem = f"{note_stem} {datetime.datetime.now().strftime('%H%M%S')}"
                    note_path = note_dir / f"{note_stem}.md"
                    print(
                        f"警告：{done_matches[0]} 已存在同名已完成筆記，"
                        f"本次改建立為 {note_path.name} 避免撞名。",
                        file=sys.stderr,
                    )

            if note_path.exists():
                note_text = note_path.read_text(encoding="utf-8")
                note_text = re.sub(
                    r"^title:.*$", f"title: {yaml_quote(display_title)}", note_text, count=1, flags=re.MULTILINE
                )
            else:
                issue_link = get_github_url(issue_num) if issue_num else ""
                note_text = (
                    "---\n"
                    f"title: {yaml_quote(display_title)}\n"
                    "done_date:\n"
                    "skills: []\n"
                    "impact:\n"
                    f"issue_link: {issue_link}\n"
                    "pr_link:\n"
                    "star: false\n"
                    "---\n"
                    "回待辦清單：[[待辦清單|待辦清單]]\n\n"
                    "## 交接內容\n\n"
                    f"{content}\n"
                )
            note_path.write_text(note_text, encoding="utf-8")

            todo_content = todo_file.read_text(encoding="utf-8")
            item_line = f"- [ ] [[{note_stem}|{display_title}]]"
            # Match either an already-linked line from a previous run of this fixed version,
            # or a legacy plain-text line left by the old (pre-fix) version of this script.
            pattern = re.compile(
                rf"^[ \t]*- \[ \] (?:\[\[{re.escape(note_stem)}[^\]]*\]\]|"
                rf"{'issue #' + issue_num + ' handoff' if issue_num else re.escape(branch) + ' handoff'}.*)$",
                re.MULTILINE,
            )

            if pattern.search(todo_content):
                new_todo = pattern.sub(item_line, todo_content, count=1)
                print(f"已更新 Obsidian 待辦清單既有項目：{item_line}")
            else:
                # Insert right before the first checkbox item
                first_item = re.search(r"^[ \t]*- \[[ x]\]", todo_content, re.MULTILINE)
                if first_item:
                    idx = first_item.start()
                    new_todo = todo_content[:idx] + item_line + "\n" + todo_content[idx:]
                else:
                    new_todo = todo_content + "\n" + item_line + "\n"
                print(f"已新增至 Obsidian 待辦清單：{item_line}")

            todo_file.write_text(new_todo, encoding="utf-8")
            print(f"已建立/更新交接筆記：{note_path}")
        except Exception as e:
            print(f"警告：更新 Obsidian 待辦清單時發生錯誤：{e}", file=sys.stderr)


def cmd_resume(args):
    repo_name, current_branch = get_git_info()
    query = args.query

    if not HANDOFF_DIR.exists():
        print(f"目前沒有任何交接檔案（目錄 {HANDOFF_DIR} 不存在）。", file=sys.stderr)
        sys.exit(1)

    target_file = None

    if query:
        # Check if query is a pure issue number
        clean_num = extract_issue_num(query) or query
        # 1. Search for matching files with that issue number in current repo first
        matches = list(HANDOFF_DIR.glob(f"{repo_name}__*{clean_num}*.md"))
        if not matches:
            # Search globally across repos
            matches = list(HANDOFF_DIR.glob(f"*{clean_num}*.md"))
        if matches:
            target_file = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    else:
        # Match current branch
        branch_slug = current_branch.replace("/", "--").replace(" ", "-")
        exact_file = HANDOFF_DIR / f"{repo_name}__{branch_slug}.md"
        if exact_file.exists():
            target_file = exact_file
        else:
            # Try issue number in current branch
            num = extract_issue_num(current_branch)
            if num:
                matches = list(HANDOFF_DIR.glob(f"{repo_name}__*{num}*.md"))
                if matches:
                    target_file = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    if target_file and target_file.exists():
        print(f"=== 找到交接檔案：{target_file.name} ===")
        print(target_file.read_text(encoding="utf-8"))
    else:
        print(f"查無符合條件的交接檔案（搜尋：{query or current_branch}）。", file=sys.stderr)
        sys.exit(1)


def mark_note_done(vault_path, issue_num, query):
    """Fill done_date on the handoff note and drop its line from Todo/待辦清單.md.

    Shared by `complete` (task finished) and `claim` (new agent took over).
    Idempotent: done_date is only filled when empty, and the todo line is only
    removed when still present.
    """
    # Mark the linked note's done_date, then drop its line from Todo/待辦清單.md —
    # this mirrors what the vault's own auto-done-date plugin does when a box is checked
    # by hand, and lets auto-move-done relocate the note into Todo/已完成/<date>/.
    todo_file = vault_path / "Todo" / "待辦清單.md"

    if todo_file.exists():
        try:
            if issue_num:
                note_stem = slugify_for_filename(f"issue #{issue_num} handoff")
            else:
                note_stem = slugify_for_filename(f"{query} handoff")

            note_candidates = list((vault_path / "Todo" / "未完成").glob(f"{note_stem}.md")) + list(
                (vault_path / "Todo" / "已完成").glob(f"**/{note_stem}.md")
            )
            if note_candidates:
                note_path = note_candidates[0]
                note_text = note_path.read_text(encoding="utf-8")
                if re.search(r"^done_date:\s*$", note_text, re.MULTILINE):
                    note_text = re.sub(
                        r"^done_date:\s*$", f"done_date: {today_str()}", note_text,
                        count=1, flags=re.MULTILINE,
                    )
                    note_path.write_text(note_text, encoding="utf-8")
                    print(f"已標記筆記完成日期：{note_path.name}")

            content = todo_file.read_text(encoding="utf-8")
            new_content = re.sub(
                rf"^[ \t]*- \[ \] \[\[{re.escape(note_stem)}[^\]]*\]\]\n?",
                "",
                content,
                flags=re.MULTILINE,
            )
            if new_content == content:
                # Legacy plain-text line left by the old (pre-fix) version of this script.
                legacy_text = f"issue #{issue_num} handoff" if issue_num else f"{re.escape(query)} handoff"
                new_content = re.sub(
                    rf"^[ \t]*- \[ \] {legacy_text}.*\n?", "", content, flags=re.MULTILINE
                )

            if new_content != content:
                todo_file.write_text(new_content, encoding="utf-8")
                print("已從 Obsidian 待辦清單移除對應的 handoff 項目（筆記已標記完成，交給 auto-move-done 外掛歸檔）。")
            else:
                print("Obsidian 待辦清單中未找到對應的未完成 handoff 項目（或已是完成狀態）。")
        except Exception as e:
            print(f"更新 Obsidian 待辦清單時發生錯誤：{e}", file=sys.stderr)


def cmd_complete(args):
    repo_name, current_branch = get_git_info()
    query = args.query or current_branch
    issue_num = extract_issue_num(query)

    # 1. Delete matching handoff files
    deleted = []
    if HANDOFF_DIR.exists():
        # Match current branch slug
        branch_slug = query.replace("/", "--").replace(" ", "-")
        exact_file = HANDOFF_DIR / f"{repo_name}__{branch_slug}.md"
        if exact_file.exists():
            exact_file.unlink()
            deleted.append(exact_file.name)

        if issue_num:
            candidates = list(HANDOFF_DIR.glob(f"{repo_name}__*{issue_num}*.md"))
            if not candidates:
                candidates = list(HANDOFF_DIR.glob(f"*{issue_num}*.md"))
            for f in candidates:
                if f.exists():
                    f.unlink()
                    deleted.append(f.name)

    if deleted:
        print(f"已清理交接檔案：{', '.join(set(deleted))}")
    else:
        print("未發現需清理的交接檔案。")

    # 2. Mark the note done and drop it from the todo list.
    vault_path = Path(args.vault) if args.vault else DEFAULT_VAULT
    mark_note_done(vault_path, issue_num, query)


def branch_from_slug(slug):
    # record() turns "/" into "--" for the filename; undo it to recover the branch.
    return slug.replace("--", "/")


def claim_handoff_file(f, vault_path):
    """Tick a handoff off the todo list WITHOUT deleting the handoff file.

    The file stays so a crashed new session can be re-fed; `complete` removes it.
    """
    branch = branch_from_slug(f.stem.split("__", 1)[1]) if "__" in f.stem else f.stem
    issue_num = extract_issue_num(branch, f.read_text(encoding="utf-8"))
    print(f"[handoff claim] {f.name}")
    mark_note_done(vault_path, issue_num, branch)


def cmd_claim(args):
    repo_name, current_branch = get_git_info()
    query = args.query or current_branch
    vault_path = Path(args.vault) if args.vault else DEFAULT_VAULT
    matches = []
    if HANDOFF_DIR.exists():
        num = extract_issue_num(query)
        matches = list(HANDOFF_DIR.glob(f"*__{query.replace('/', '--')}.md"))
        if not matches and num:
            matches = list(HANDOFF_DIR.glob(f"*__*{num}*.md"))
    if not matches:
        print(f"查無符合的交接檔案（搜尋：{query}）。", file=sys.stderr)
        sys.exit(1)
    for f in matches:
        claim_handoff_file(f, vault_path)


def cmd_hook_claim(args):
    """UserPromptSubmit hook: if the prompt carries a pasted handoff, claim it.

    Reads hook JSON from stdin. Never fails the prompt (always exits 0) and
    prints nothing when the prompt has no handoff.
    """
    import json

    try:
        prompt = json.load(sys.stdin).get("prompt", "") or ""
    except Exception:
        return
    if not prompt or not HANDOFF_DIR.exists():
        return

    vault_path = DEFAULT_VAULT
    claimed = []
    for f in HANDOFF_DIR.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        # Signals: the file name/path was pasted, or a distinctive chunk of its content was.
        if f.name in prompt or (len(content) >= 80 and content[:200] in prompt):
            claimed.append(f)
    # Also accept a pasted Obsidian note name: "issue -<num> handoff".
    for m in re.finditer(r"issue -(\d+) handoff", prompt):
        for f in HANDOFF_DIR.glob(f"*__*{m.group(1)}*.md"):
            if f not in claimed:
                claimed.append(f)

    for f in claimed:
        try:
            claim_handoff_file(f, vault_path)
        except Exception as e:
            print(f"[handoff claim] 失敗 {f.name}: {e}", file=sys.stderr)


def cmd_list(args):
    if not HANDOFF_DIR.exists():
        print("目前沒有任何交接紀錄。")
        return

    files = sorted(HANDOFF_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("目前沒有任何交接紀錄。")
        return

    print(f"=== 目前待接手的 Handoff 清單（共 {len(files)} 筆）===")
    for f in files:
        parts = f.stem.split("__", 1)
        repo = parts[0]
        branch = parts[1] if len(parts) > 1 else ""
        content = f.read_text(encoding="utf-8")
        summary = extract_summary_from_content(content)
        mtime = os.path.getmtime(f)
        import datetime
        dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"- [{dt}] {repo} | {branch}")
        print(f"  摘要: {summary}")
        print(f"  指令: /handoff resume {branch}")


def main():
    parser = argparse.ArgumentParser(description="Claude Code Handoff Manager")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # record
    p_rec = subparsers.add_parser("record", help="Record a handoff")
    p_rec.add_argument("file", nargs="?", help="Path to handoff markdown file (default: stdin)")
    p_rec.add_argument("--repo", help="Override repository name")
    p_rec.add_argument("--branch", help="Override branch name")
    p_rec.add_argument("--issue", help="Override issue number")
    p_rec.add_argument("--summary", help="One-line summary for Todo")
    p_rec.add_argument("--vault", help="Path to Obsidian vault")

    # resume
    p_res = subparsers.add_parser("resume", help="Resume a handoff")
    p_res.add_argument("query", nargs="?", help="Issue number or branch name")

    # complete
    p_com = subparsers.add_parser("complete", help="Complete and clean up a handoff")
    p_com.add_argument("query", nargs="?", help="Issue number or branch name")
    p_com.add_argument("--vault", help="Path to Obsidian vault")

    # claim: new agent took over -> tick + move to done, keep the handoff file
    p_cla = subparsers.add_parser("claim", help="Mark handoff as taken over (keeps the file)")
    p_cla.add_argument("query", nargs="?", help="Issue number or branch name")
    p_cla.add_argument("--vault", help="Path to Obsidian vault")

    # hook-claim: UserPromptSubmit hook entry (reads hook JSON from stdin)
    subparsers.add_parser("hook-claim", help="Hook entry: claim handoffs found in the prompt")

    # list
    subparsers.add_parser("list", help="List all pending handoffs")

    args = parser.parse_args()
    if args.action == "record":
        cmd_record(args)
    elif args.action == "resume":
        cmd_resume(args)
    elif args.action == "complete":
        cmd_complete(args)
    elif args.action == "claim":
        cmd_claim(args)
    elif args.action == "hook-claim":
        cmd_hook_claim(args)
    elif args.action == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
