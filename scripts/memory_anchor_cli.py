#!/usr/bin/env python3
"""
Memory Anchor CLI - 记忆管理命令行工具

用法：
    memory-anchor harvest --all          收割所有项目的 CLAUDE.md
    memory-anchor harvest --project PATH 收割指定项目
    memory-anchor sync --to-files        将 Qdrant 同步到 .memos/
    memory-anchor sync --from-files      从 .memos/ 导入到 Qdrant
    memory-anchor sync --status          检查同步状态
    memory-anchor status                 查看 Qdrant 状态
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")


def cmd_harvest(args):
    """收割 CLAUDE.md 中的记忆"""
    from scripts.harvest_memories import harvest_project, discover_projects

    print("🌾 Memory Harvest")
    print(f"   Qdrant URL: {os.environ.get('QDRANT_URL', 'Not set')}")

    if args.dry_run:
        print("   模式: 干运行（不写入）")

    total_found = 0
    total_indexed = 0

    if args.all:
        projects = discover_projects()
        print(f"\n发现 {len(projects)} 个项目")

        for project in projects:
            found, indexed = harvest_project(
                project,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            total_found += found
            total_indexed += indexed
    elif args.project:
        project_path = Path(args.project).expanduser().resolve()
        if not project_path.exists():
            print(f"❌ 项目不存在: {project_path}")
            sys.exit(1)

        found, indexed = harvest_project(
            project_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        total_found += found
        total_indexed += indexed

    print(f"\n📊 收割完成")
    print(f"   发现记忆: {total_found}")
    print(f"   写入记忆: {total_indexed}")


def cmd_sync(args):
    """同步记忆"""
    from backend.services.search import SearchService
    from backend.config import reset_config

    project_path = Path(args.project or os.getcwd()).resolve()
    memos_dir = project_path / ".memos"

    # 从项目路径提取项目 ID 并设置环境变量
    project_id = "".join(
        c for c in project_path.name if c.isalnum() or c in ("_", "-")
    ) or "default"
    os.environ["MCP_MEMORY_PROJECT_ID"] = project_id

    if args.status:
        # 检查同步状态
        print("📊 同步状态检查")
        print(f"   项目: {project_path}")

        # Qdrant 状态
        try:
            reset_config()
            service = SearchService()
            stats = service.get_stats()
            print(f"\n   Qdrant:")
            print(f"     - Collection: {stats['collection_name']}")
            print(f"     - 模式: {stats['mode']}")
            print(f"     - 记录数: {stats['total_count']}")
        except Exception as e:
            print(f"     - ❌ 连接失败: {e}")

        # .memos 状态
        if memos_dir.exists():
            files = list(memos_dir.glob("*.md"))
            print(f"\n   .memos/:")
            print(f"     - 文件数: {len(files)}")
            for f in files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                print(f"     - {f.name}: {mtime.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"\n   .memos/: 不存在")

    elif args.to_files:
        # 同步到文件
        changed_only = getattr(args, "changed_only", False)
        print(f"📤 同步 Qdrant → .memos/ {'(增量)' if changed_only else '(全量)'}")
        print(f"   项目: {project_path}")

        memos_dir.mkdir(parents=True, exist_ok=True)

        reset_config()
        service = SearchService()

        # 读取上次同步时间
        last_sync = None
        sync_meta_file = memos_dir / ".sync_metadata.json"
        if changed_only and sync_meta_file.exists():
            import json
            try:
                meta = json.loads(sync_meta_file.read_text())
                last_sync = meta.get("last_sync")
                print(f"   上次同步: {last_sync}")
            except Exception:
                pass

        # 获取各层记忆
        sync_time = datetime.now().isoformat()
        all_notes = []

        for layer in ["fact", "session"]:
            notes = service.list_notes(layer=layer, limit=500)

            # 增量过滤
            if changed_only and last_sync:
                notes = [
                    n for n in notes
                    if (n.get("created_at") or "") > last_sync
                ]

            all_notes.extend(notes)
            print(f"   {layer}: {len(notes)} 条")

        if not all_notes and changed_only:
            print("\n✅ 无变更，跳过同步")
        else:
            # 写入文件
            _write_memos_files(memos_dir, all_notes, sync_time)

            # 保存同步元数据
            import json
            sync_meta_file.write_text(json.dumps({
                "last_sync": sync_time,
                "notes_count": len(all_notes),
            }))

            print(f"\n✅ 同步完成，输出到 {memos_dir}")

    elif args.from_files:
        # 从文件导入
        print("📥 同步 .memos/ → Qdrant")
        print(f"   项目: {project_path}")

        if not memos_dir.exists():
            print(f"❌ .memos/ 目录不存在")
            sys.exit(1)

        reset_config()
        service = SearchService()

        imported = 0
        skipped = 0

        # 解析 fact.md 和 session.md
        for layer in ["fact", "session"]:
            md_file = memos_dir / f"{layer}.md"
            if not md_file.exists():
                print(f"   ⏭️ {layer}.md 不存在，跳过")
                continue

            content = md_file.read_text(encoding="utf-8")
            notes = _parse_memos_md(content, layer)

            print(f"   {layer}: 解析到 {len(notes)} 条记忆")

            for note in notes:
                try:
                    # 生成幂等 ID
                    note_id = _generate_note_id(project_path.name, note["content"])

                    # 检查是否已存在
                    existing = service.get_note(note_id)
                    if existing:
                        skipped += 1
                        continue

                    # 写入
                    service.index_note(
                        note_id=note_id,
                        content=note["content"],
                        layer=note["layer"],
                        category=note.get("category"),
                        source=f"memos:{layer}.md",
                    )
                    imported += 1

                except Exception as e:
                    print(f"   ⚠️ 导入失败: {e}")

        print(f"\n✅ 导入完成")
        print(f"   导入: {imported} 条")
        print(f"   跳过（已存在）: {skipped} 条")


def _write_memos_files(memos_dir: Path, notes: list, sync_time: str):
    """写入 .memos/ 文件"""
    # 按层级分组
    fact_notes = [n for n in notes if n.get("layer") == "fact"]
    session_notes = [n for n in notes if n.get("layer") == "session"]

    # 写入 fact.md
    fact_content = _format_notes_md(fact_notes, "事实层记忆", sync_time)
    (memos_dir / "fact.md").write_text(fact_content, encoding="utf-8")

    # 写入 session.md
    session_content = _format_notes_md(session_notes, "会话层记忆", sync_time)
    (memos_dir / "session.md").write_text(session_content, encoding="utf-8")

    # 写入 index.md
    index_content = _format_index_md(notes, sync_time)
    (memos_dir / "index.md").write_text(index_content, encoding="utf-8")


def _format_notes_md(notes: list, title: str, sync_time: str) -> str:
    """格式化记忆为 Markdown"""
    lines = [
        f"# {title}",
        "",
        f"> 同步时间: {sync_time}",
        f"> 记录数: {len(notes)}",
        "",
        "---",
        "",
    ]

    if not notes:
        lines.append("*暂无记录*")
        return "\n".join(lines)

    # 按类别分组
    by_category: dict = {}
    for note in notes:
        cat = note.get("category") or "未分类"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(note)

    for category, cat_notes in sorted(by_category.items()):
        lines.append(f"## {category}")
        lines.append("")
        for note in cat_notes:
            content = note.get("content", "")
            lines.append(f"- {content}")
        lines.append("")

    return "\n".join(lines)


def _format_index_md(notes: list, sync_time: str) -> str:
    """格式化索引"""
    lines = [
        "# Memory Anchor 索引",
        "",
        f"> 同步时间: {sync_time}",
        "",
        "---",
        "",
    ]

    # 统计
    layer_count: dict = {}
    for note in notes:
        layer = note.get("layer") or "unknown"
        layer_count[layer] = layer_count.get(layer, 0) + 1

    lines.append("## 统计")
    lines.append("")
    for layer, count in sorted(layer_count.items()):
        icon = {"constitution": "🔴", "fact": "🔵", "session": "🟢"}.get(layer, "⚪")
        lines.append(f"- {icon} {layer}: {count} 条")
    lines.append("")

    lines.append("## 文件")
    lines.append("")
    lines.append("- [fact.md](./fact.md) - 事实层记忆")
    lines.append("- [session.md](./session.md) - 会话层记忆")
    lines.append("")

    return "\n".join(lines)


def _parse_memos_md(content: str, layer: str) -> list[dict]:
    """
    解析 .memos/*.md 文件，提取记忆条目。

    格式示例：
    ## person
    - 患者女儿王小红，电话13800138000

    ## event
    - 修复了 search_memory 空查询问题
    """
    import re

    notes = []
    current_category = None

    for line in content.split("\n"):
        line = line.strip()

        # 解析类别标题
        if line.startswith("## "):
            current_category = line[3:].strip()
            # 跳过非类别标题
            if current_category in ["统计", "文件"]:
                current_category = None
            continue

        # 解析记忆条目
        if line.startswith("- ") and current_category:
            note_content = line[2:].strip()
            if note_content and not note_content.startswith("*"):  # 跳过元信息
                notes.append({
                    "content": note_content,
                    "layer": layer,
                    "category": current_category if current_category != "未分类" else None,
                })

    return notes


def _generate_note_id(project_id: str, content: str):
    """生成幂等的 note ID"""
    import hashlib
    from uuid import UUID, uuid5

    NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    return uuid5(NAMESPACE, f"{project_id}:{content_hash}")


def cmd_status(args):
    """查看 Qdrant 状态"""
    import httpx

    qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")

    print("📊 Memory Anchor 状态")
    print(f"   Qdrant URL: {qdrant_url}")

    try:
        with httpx.Client(timeout=3.0) as client:
            # 检查健康状态
            resp = client.get(f"{qdrant_url}/readyz")
            if resp.status_code == 200:
                print("   状态: ✅ 运行中")
            else:
                print("   状态: ⚠️ 未就绪")
                return

            # 获取 collections
            resp = client.get(f"{qdrant_url}/collections")
            if resp.status_code == 200:
                data = resp.json()
                collections = data.get("result", {}).get("collections", [])
                memory_collections = [
                    c for c in collections if c.get("name", "").startswith("memory_anchor")
                ]

                print(f"\n   Memory Anchor Collections ({len(memory_collections)}):")
                for c in memory_collections:
                    name = c.get("name", "unknown")
                    # 提取项目名
                    project = name.replace("memory_anchor_notes_", "") or "default"
                    print(f"     - {project}")

    except Exception as e:
        print(f"   状态: ❌ 离线")
        print(f"   错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Memory Anchor CLI - 记忆管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  memory-anchor harvest --all              收割所有项目
  memory-anchor harvest --project ~/跨境2  收割指定项目
  memory-anchor sync --status              检查同步状态
  memory-anchor sync --to-files            同步到 .memos/
  memory-anchor status                     查看 Qdrant 状态
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # harvest 子命令
    harvest_parser = subparsers.add_parser("harvest", help="收割 CLAUDE.md 中的记忆")
    harvest_group = harvest_parser.add_mutually_exclusive_group(required=True)
    harvest_group.add_argument("--all", action="store_true", help="收割所有项目")
    harvest_group.add_argument("--project", type=str, help="收割指定项目")
    harvest_parser.add_argument("--dry-run", action="store_true", help="干运行")
    harvest_parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    # sync 子命令
    sync_parser = subparsers.add_parser("sync", help="同步记忆")
    sync_group = sync_parser.add_mutually_exclusive_group(required=True)
    sync_group.add_argument("--to-files", action="store_true", help="Qdrant → .memos/")
    sync_group.add_argument("--from-files", action="store_true", help=".memos/ → Qdrant")
    sync_group.add_argument("--status", action="store_true", help="检查同步状态")
    sync_parser.add_argument("--project", type=str, help="项目路径（默认当前目录）")
    sync_parser.add_argument("--changed-only", action="store_true", help="仅同步变更（增量同步）")

    # status 子命令
    status_parser = subparsers.add_parser("status", help="查看 Qdrant 状态")

    args = parser.parse_args()

    if args.command == "harvest":
        cmd_harvest(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
