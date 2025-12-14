#!/usr/bin/env python3
"""
初始化宪法层到 Qdrant

从 ~/.memory-anchor/projects/global/constitution.yaml 读取宪法层条目，
写入到 Qdrant 的 global collection。
"""

import os
import sys
from pathlib import Path
from uuid import uuid5, UUID

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")
os.environ.setdefault("MCP_MEMORY_PROJECT_ID", "global")

import yaml
from backend.config import reset_config
from backend.services.search import SearchService

# 用于生成幂等 ID 的命名空间
NAMESPACE_CONSTITUTION = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c9")


def main():
    # 读取宪法层配置
    config_path = Path.home() / ".memory-anchor" / "projects" / "global" / "constitution.yaml"

    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    constitution_items = config.get("constitution", [])

    if not constitution_items:
        print("⚠️ 没有找到宪法层条目")
        sys.exit(0)

    print(f"📜 初始化宪法层: {len(constitution_items)} 条")

    # 重置配置以使用 global 项目
    reset_config()

    # 创建 SearchService
    service = SearchService()

    # 准备批量写入
    notes = []
    for item in constitution_items:
        item_id = item.get("id", str(len(notes)))
        note_id = uuid5(NAMESPACE_CONSTITUTION, f"global:{item_id}")

        notes.append({
            "id": note_id,
            "content": item.get("content", ""),
            "layer": "constitution",  # 宪法层
            "category": item.get("category", "routine"),
            "is_active": True,
            "confidence": 1.0,  # 宪法层置信度最高
            "source": f"constitution:{item_id}",
        })

    # 批量写入
    indexed = service.index_notes_batch(notes)

    print(f"✅ 写入 {indexed} 条宪法层条目到 collection: {service.collection_name}")

    # 验证
    stats = service.get_stats()
    print(f"📊 Collection 统计: {stats}")


if __name__ == "__main__":
    main()
