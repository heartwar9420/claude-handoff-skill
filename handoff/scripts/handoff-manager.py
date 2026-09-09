#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handoff Manager for Claude Code.
Handles recording, resuming, listing, and completing handoff summaries,
with seamless integration into Obsidian Todo/待辦清單.md.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_VAULT = Path.home() / "Documents" / "obsidian-vault"
HANDOFF_DIR = Path.home() / ".claude" / "handoffs"


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
        r"##\s*(?:2\.\s*)?Next\s*Steps\s*\n(.*?)(?=\n##|\Z)",
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
        r"##\s*(?:4\.\s*)?Suggested\s*first\s*prompt\s*\n.*?```(?:text)?\s*\n(.*?)\n```",
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
            todo_content = todo_file.read_text(encoding="utf-8")
            if issue_num:
                item_line = f"- [ ] issue #{issue_num} handoff ({summary})"
                pattern = re.compile(
                    rf"^[ \t]*- \[ \] issue #{issue_num} handoff.*$", re.MULTILINE
                )
            else:
                item_line = f"- [ ] {branch} handoff ({summary})"
                pattern = re.compile(
                    rf"^[ \t]*- \[ \] {re.escape(branch)} handoff.*$", re.MULTILINE
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

    # 2. Update Obsidian Todo/待辦清單.md
    vault_path = Path(args.vault) if args.vault else DEFAULT_VAULT
    todo_file = vault_path / "Todo" / "待辦清單.md"

    if todo_file.exists():
        try:
            content = todo_file.read_text(encoding="utf-8")
            if issue_num:
                pattern = re.compile(
                    rf"^[ \t]*- \[ \] (issue #{issue_num} handoff.*)$", re.MULTILINE
                )
            else:
                pattern = re.compile(
                    rf"^[ \t]*- \[ \] ({re.escape(query)} handoff.*)$", re.MULTILINE
                )

            new_content = pattern.sub(r"- [x] \1", content)
            if new_content != content:
                todo_file.write_text(new_content, encoding="utf-8")
                print("已將 Obsidian 待辦清單中對應的 handoff 項目標記為已完成 (- [x])。")
            else:
                print("Obsidian 待辦清單中未找到對應的未完成 handoff 項目（或已是完成狀態）。")
        except Exception as e:
            print(f"更新 Obsidian 待辦清單時發生錯誤：{e}", file=sys.stderr)


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

    # list
    subparsers.add_parser("list", help="List all pending handoffs")

    args = parser.parse_args()
    if args.action == "record":
        cmd_record(args)
    elif args.action == "resume":
        cmd_resume(args)
    elif args.action == "complete":
        cmd_complete(args)
    elif args.action == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
