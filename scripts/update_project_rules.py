#!/usr/bin/env python3
"""
批量更新项目 CLAUDE.md 添加记忆同步规则引用

用法：
    python scripts/update_project_rules.py --all
    python scripts/update_project_rules.py --project ~/projects/跨境2
    python scripts/update_project_rules.py --dry-run --all
"""

import argparse
import sys
from pathlib import Path

# 要添加到 CLAUDE.md 的记忆同步规则块
MEMORY_SYNC_BLOCK = '''
---

## 记忆同步规则（自动继承）

> 本项目遵循全局记忆同步规则，详见 `~/.claude/rules/13-memory-sync.md`

### 快速参考

- **Qdrant** 是记忆单一真相源
- **`.memos/`** 是人类可读备份
- 任务完成后调用 `add_memory` 写入
- 会话开始时调用 `search_memory` 加载上下文

### 记忆块规范

在本文件中使用结构化记忆块：

```memory-anchor
id: unique-id
type: decision | bugfix | refactor | discovery | note
summary: 一句话总结
layer: fact | session
tags: [tag1, tag2]
```
'''

# 检测标记，用于判断是否已添加
MARKER = "## 记忆同步规则（自动继承）"

# 项目根目录
PROJECTS_ROOT = Path.home() / "projects"

# 排除的目录
EXCLUDE_DIRS = ["node_modules", ".venv", "__pycache__", ".git", ".qdrant"]


def should_update(claude_md: Path) -> bool:
    """检查是否需要更新"""
    try:
        content = claude_md.read_text(encoding="utf-8")
        return MARKER not in content
    except Exception:
        return False


def update_claude_md(claude_md: Path, dry_run: bool = False) -> bool:
    """更新 CLAUDE.md 文件"""
    try:
        content = claude_md.read_text(encoding="utf-8")

        # 已经包含记忆同步规则
        if MARKER in content:
            return False

        # 追加规则块
        new_content = content.rstrip() + "\n" + MEMORY_SYNC_BLOCK

        if dry_run:
            print(f"   [DRY-RUN] 将添加记忆同步规则块")
            return True

        claude_md.write_text(new_content, encoding="utf-8")
        return True

    except Exception as e:
        print(f"   ❌ 更新失败: {e}")
        return False


def discover_projects() -> list[Path]:
    """发现所有有 CLAUDE.md 的项目"""
    projects = []

    if not PROJECTS_ROOT.exists():
        return projects

    for item in PROJECTS_ROOT.iterdir():
        if item.is_dir() and item.name not in EXCLUDE_DIRS:
            claude_md = item / "CLAUDE.md"
            if claude_md.exists():
                projects.append(item)

    return projects


def main():
    parser = argparse.ArgumentParser(description="更新项目 CLAUDE.md 添加记忆同步规则")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="更新所有项目")
    group.add_argument("--project", type=Path, help="更新指定项目")
    parser.add_argument("--dry-run", action="store_true", help="干运行，不实际修改")

    args = parser.parse_args()

    print("📝 更新项目 CLAUDE.md")

    if args.dry_run:
        print("   模式: 干运行（不修改文件）")

    updated = 0
    skipped = 0

    if args.all:
        projects = discover_projects()
        print(f"\n发现 {len(projects)} 个项目")

        for project in projects:
            claude_md = project / "CLAUDE.md"
            print(f"\n📂 {project.name}")

            if not should_update(claude_md):
                print("   ⏭️ 已包含记忆同步规则，跳过")
                skipped += 1
                continue

            if update_claude_md(claude_md, dry_run=args.dry_run):
                print("   ✅ 已添加记忆同步规则")
                updated += 1

    else:
        project_path = args.project.expanduser().resolve()
        claude_md = project_path / "CLAUDE.md"

        if not claude_md.exists():
            print(f"❌ CLAUDE.md 不存在: {claude_md}")
            sys.exit(1)

        print(f"\n📂 {project_path.name}")

        if not should_update(claude_md):
            print("   ⏭️ 已包含记忆同步规则")
            skipped += 1
        elif update_claude_md(claude_md, dry_run=args.dry_run):
            print("   ✅ 已添加记忆同步规则")
            updated += 1

    print(f"\n📊 完成")
    print(f"   更新: {updated}")
    print(f"   跳过: {skipped}")


if __name__ == "__main__":
    main()
