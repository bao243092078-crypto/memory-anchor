#!/usr/bin/env python3
"""
Memory Anchor 每日备份脚本

功能：
1. 同步所有项目的 Qdrant 记忆到 .memos/
2. 备份 Qdrant 数据目录
3. 清理过期的会话层记忆

由 launchd 每天自动执行
"""

import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")

# 配置
PROJECTS_ROOT = Path.home() / "projects"
BACKUP_DIR = Path.home() / ".memory-anchor" / "backups"
QDRANT_STORAGE = Path.home() / ".qdrant_storage"
MAX_BACKUPS = 7  # 保留最近 7 天的备份
SESSION_EXPIRE_HOURS = 24  # 会话层过期时间


def sync_all_projects():
    """同步所有项目的记忆到 .memos/"""
    from backend.config import reset_config
    from backend.services.search import SearchService

    print("📤 同步所有项目...")

    synced = 0
    for project_dir in PROJECTS_ROOT.iterdir():
        if not project_dir.is_dir():
            continue

        # 跳过隐藏目录和常见排除目录
        if project_dir.name.startswith("."):
            continue
        if project_dir.name in ["node_modules", ".venv", "__pycache__"]:
            continue

        memos_dir = project_dir / ".memos"

        try:
            # 设置项目 ID
            project_id = "".join(
                c for c in project_dir.name if c.isalnum() or c in ("_", "-")
            ) or "default"
            os.environ["MCP_MEMORY_PROJECT_ID"] = project_id
            reset_config()

            service = SearchService()
            stats = service.get_stats()

            if stats.get("total_count", 0) == 0:
                continue

            # 创建 .memos 目录
            memos_dir.mkdir(parents=True, exist_ok=True)

            # 获取记忆
            all_notes = []
            for layer in ["fact", "session"]:
                notes = service.list_notes(layer=layer, limit=500)
                all_notes.extend(notes)

            if all_notes:
                _write_memos(memos_dir, all_notes)
                synced += 1
                print(f"   ✅ {project_dir.name}: {len(all_notes)} 条")

        except Exception as e:
            print(f"   ⚠️ {project_dir.name}: {e}")

    print(f"\n   同步完成: {synced} 个项目")


def _write_memos(memos_dir: Path, notes: list):
    """写入 .memos/ 文件"""
    sync_time = datetime.now().isoformat()

    # 按层级分组
    fact_notes = [n for n in notes if n.get("layer") == "fact"]
    session_notes = [n for n in notes if n.get("layer") == "session"]

    # 写入 fact.md
    fact_lines = [
        "# 事实层记忆",
        "",
        f"> 同步: {sync_time}",
        "",
    ]
    for n in fact_notes:
        fact_lines.append(f"- {n.get('content', '')}")
    (memos_dir / "fact.md").write_text("\n".join(fact_lines), encoding="utf-8")

    # 写入 session.md
    session_lines = [
        "# 会话层记忆",
        "",
        f"> 同步: {sync_time}",
        "",
    ]
    for n in session_notes:
        session_lines.append(f"- {n.get('content', '')}")
    (memos_dir / "session.md").write_text("\n".join(session_lines), encoding="utf-8")


def backup_qdrant():
    """备份 Qdrant 数据目录"""
    if not QDRANT_STORAGE.exists():
        print("⏭️ Qdrant 存储目录不存在，跳过备份")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_name = f"qdrant_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = BACKUP_DIR / backup_name

    print(f"💾 备份 Qdrant 数据...")
    print(f"   源: {QDRANT_STORAGE}")
    print(f"   目标: {backup_path}")

    try:
        # 只备份 collections 目录（排除 WAL 等临时文件）
        collections_dir = QDRANT_STORAGE / "collections"
        if collections_dir.exists():
            shutil.copytree(collections_dir, backup_path / "collections")
            print(f"   ✅ 备份完成")
        else:
            print(f"   ⏭️ 无 collections 目录")
    except Exception as e:
        print(f"   ⚠️ 备份失败: {e}")


def cleanup_old_backups():
    """清理过期备份"""
    if not BACKUP_DIR.exists():
        return

    backups = sorted(BACKUP_DIR.iterdir(), reverse=True)
    if len(backups) <= MAX_BACKUPS:
        return

    print(f"🧹 清理过期备份...")
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            shutil.rmtree(old_backup)
            print(f"   删除: {old_backup.name}")
        except Exception as e:
            print(f"   ⚠️ 清理失败 {old_backup.name}: {e}")


def main():
    print("=" * 50)
    print(f"Memory Anchor 每日备份 - {datetime.now().isoformat()}")
    print("=" * 50)

    sync_all_projects()
    backup_qdrant()
    cleanup_old_backups()

    print("\n✅ 每日备份完成")


if __name__ == "__main__":
    main()
