#!/usr/bin/env python3
"""
Memory Anchor Stop Hook - 会话结束处理

当前实现：
1. 生成会话摘要
2. （Phase 3 扩展）自动写入 Memory Anchor
3. （Phase 3 扩展）提取未完成任务

用法：
    from backend.hooks import get_hook_registry, StopHook

    registry = get_hook_registry()
    registry.register(StopHook())

    # 会话结束时
    context = HookContext(hook_type=HookType.STOP, session_id="session-123")
    result = registry.execute_single(HookType.STOP, context)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.hooks.base import (
    BaseHook,
    HookContext,
    HookResult,
    HookType,
)

logger = logging.getLogger(__name__)

# 状态文件目录
STATE_DIR = Path.home() / ".memory-anchor" / "state"


def ensure_state_dir() -> Path:
    """确保状态目录存在"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def generate_session_summary(
    session_id: str,
    modified_files: list[dict[str, Any]] | None = None,
    memory_operations: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成会话摘要

    Args:
        session_id: 会话 ID
        modified_files: 修改的文件列表（从 PostToolHook 获取）
        memory_operations: memory 操作列表（从 PostToolHook 获取）
        metadata: 额外元数据

    Returns:
        会话摘要字典
    """
    modified_files = modified_files or []
    memory_operations = memory_operations or []
    metadata = metadata or {}

    # 统计文件修改
    source_files = [
        f["file"]
        for f in modified_files
        if f.get("is_source") and not f.get("is_test")
    ]
    test_files = [f["file"] for f in modified_files if f.get("is_test")]

    # 生成摘要
    summary = {
        "session_id": session_id,
        "ended_at": datetime.now().isoformat(),
        "statistics": {
            "total_file_modifications": len(modified_files),
            "source_files_modified": len(set(source_files)),
            "test_files_modified": len(set(test_files)),
            "memory_operations": len(memory_operations),
        },
        "files": {
            "source": list(set(source_files)),
            "test": list(set(test_files)),
        },
        "memory_operations": [
            {
                "tool": op.get("tool"),
                "timestamp": op.get("timestamp"),
            }
            for op in memory_operations
        ],
        "metadata": metadata,
    }

    return summary


def save_session_summary(summary: dict[str, Any]) -> Path:
    """保存会话摘要到文件

    Args:
        summary: 会话摘要

    Returns:
        保存的文件路径
    """
    state_dir = ensure_state_dir()
    session_id = summary.get("session_id", "unknown")

    # 使用时间戳避免文件名冲突
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.json"
    file_path = state_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"Session summary saved: {file_path}")
    return file_path


class StopHook(BaseHook):
    """Stop Hook - 会话结束处理

    职责：
    1. 收集会话统计信息
    2. 生成会话摘要
    3. 保存会话状态
    4. （Phase 3）写入 Memory Anchor
    """

    def __init__(self, post_tool_hook: Any | None = None):
        """初始化 StopHook

        Args:
            post_tool_hook: PostToolHook 实例，用于获取文件修改历史
        """
        self._post_tool_hook = post_tool_hook

    @property
    def hook_type(self) -> HookType:
        return HookType.STOP

    @property
    def name(self) -> str:
        return "StopHook"

    @property
    def priority(self) -> int:
        # 较低优先级，让其他 Stop hook 先执行
        return 100

    def set_post_tool_hook(self, post_tool_hook: Any) -> None:
        """设置 PostToolHook 引用"""
        self._post_tool_hook = post_tool_hook

    def execute(self, context: HookContext) -> HookResult:
        """执行会话结束处理"""
        session_id = context.session_id or "unknown"

        # 获取文件修改历史
        modified_files: list[dict[str, Any]] = []
        memory_operations: list[dict[str, Any]] = []

        if self._post_tool_hook is not None:
            try:
                modified_files = self._post_tool_hook.get_modified_files()
                memory_operations = self._post_tool_hook.get_memory_operations()
            except AttributeError:
                logger.warning("PostToolHook does not have expected methods")

        # 从 context 获取额外元数据
        metadata = context.metadata or {}

        # 生成会话摘要
        summary = generate_session_summary(
            session_id=session_id,
            modified_files=modified_files,
            memory_operations=memory_operations,
            metadata=metadata,
        )

        # 保存摘要
        try:
            file_path = save_session_summary(summary)
            message = self._format_summary_message(summary)

            return HookResult.notify(
                message=message,
                reason=f"session_summary_saved:{file_path}",
            )
        except Exception as e:
            logger.error(f"Failed to save session summary: {e}")
            return HookResult.notify(
                message=f"Session summary generation failed: {e}",
                reason="session_summary_error",
            )

    def _format_summary_message(self, summary: dict[str, Any]) -> str:
        """格式化摘要消息"""
        stats = summary.get("statistics", {})
        files = summary.get("files", {})

        lines = [
            "📊 **会话摘要**",
            "",
            f"- 文件修改: {stats.get('total_file_modifications', 0)} 次",
            f"- 源文件: {stats.get('source_files_modified', 0)} 个",
            f"- 测试文件: {stats.get('test_files_modified', 0)} 个",
            f"- Memory 操作: {stats.get('memory_operations', 0)} 次",
        ]

        source_files = files.get("source", [])
        if source_files:
            lines.append("")
            lines.append("**修改的源文件**:")
            for f in source_files[:5]:  # 最多显示 5 个
                lines.append(f"  - {f}")
            if len(source_files) > 5:
                lines.append(f"  - ... 还有 {len(source_files) - 5} 个")

        return "\n".join(lines)


__all__ = [
    "StopHook",
    "generate_session_summary",
    "save_session_summary",
]
