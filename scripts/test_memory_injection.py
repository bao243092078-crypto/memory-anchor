#!/usr/bin/env python3
"""
测试 Memory Anchor 注入 - 验证各 AI 都能获取记忆

用法：
    python scripts/test_memory_injection.py
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.sdk import MemoryClient


def test_memory_access():
    """测试记忆访问"""
    print("=" * 60)
    print("🧪 Memory Anchor 注入测试")
    print("=" * 60)

    client = MemoryClient(agent_id="test")

    # 1. 测试宪法层
    print("\n📋 宪法层（核心身份）：")
    constitution = client.get_constitution()
    if constitution:
        for m in constitution:
            print(f"  🔴 {m['content']}")
    else:
        print("  （空）")

    # 2. 测试搜索
    print("\n🔍 搜索测试（query='记忆'）：")
    results = client.search_memory(query="记忆", limit=5)
    if results:
        for m in results:
            score = m.get('score', 0)
            layer = m.get('layer', 'unknown')
            icon = {"constitution": "🔴", "fact": "🔵", "session": "🟢"}.get(layer, "⚪")
            print(f"  {icon} [{layer}] (相关度: {score:.2f}) {m['content'][:50]}...")
    else:
        print("  （无结果）")

    # 3. 统计
    print("\n📊 统计：")
    print(f"  宪法层: {len(constitution)} 条")
    print(f"  搜索结果: {len(results)} 条")

    print("\n" + "=" * 60)
    print("✅ 测试完成！Memory Anchor 可正常访问。")
    print("=" * 60)

    # 4. 打印注入模板示例
    print("\n📝 示例注入 Prompt（复制到任何 AI）：")
    print("-" * 60)
    print(format_injection_prompt(constitution, results, "你的任务描述"))
    print("-" * 60)


def format_injection_prompt(constitution: list, relevant: list, task: str) -> str:
    """格式化注入 prompt"""
    lines = ["## 你的外挂海马体（Memory Anchor）\n"]

    lines.append("### 🔴 宪法层")
    if constitution:
        for m in constitution:
            lines.append(f"- {m['content']}")
    else:
        lines.append("（空）")
    lines.append("")

    lines.append("### 🔵 相关记忆")
    if relevant:
        for m in relevant[:3]:  # 只取前3条
            lines.append(f"- {m['content'][:100]}")
    else:
        lines.append("（无）")
    lines.append("")

    lines.append(f"### 任务\n{task}")

    return "\n".join(lines)


if __name__ == "__main__":
    test_memory_access()
