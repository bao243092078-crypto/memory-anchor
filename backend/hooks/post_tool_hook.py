#!/usr/bin/env python3
"""
Memory Anchor PostToolUse Hook - 工具执行后处理

当前实现：
1. 记录工具执行结果
2. 检测文件修改操作
3. （Phase 5 扩展）生成测试建议

用法：
    from backend.hooks import get_hook_registry, PostToolHook

    registry = get_hook_registry()
    registry.register(PostToolHook())
"""

from __future__ import annotations

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

# 文件修改相关工具
FILE_MODIFY_TOOLS = {
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
}

# 需要记录的 memory-anchor 工具
MEMORY_TOOLS = {
    "add_memory",
    "delete_memory",
    "propose_constitution_change",
    "log_event",
    "promote_to_fact",
    "create_checklist_item",
}


def extract_modified_files(tool_name: str, tool_input: dict[str, Any]) -> list[str]:
    """从工具输入中提取被修改的文件路径"""
    files: list[str] = []

    if tool_name in ("Write", "Edit", "NotebookEdit"):
        file_path = tool_input.get("file_path")
        if file_path:
            files.append(file_path)

    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        for edit in edits:
            if isinstance(edit, dict) and "file_path" in edit:
                files.append(edit["file_path"])

    return files


def is_test_file(file_path: str) -> bool:
    """判断是否是测试文件"""
    path = Path(file_path)
    name = path.name.lower()
    # 检查路径中的测试目录
    path_lower = file_path.lower()
    in_test_dir = "/tests/" in path_lower or "/__tests__/" in path_lower or path_lower.startswith("__tests__/")
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.js")
        or in_test_dir
    )


def is_source_file(file_path: str) -> bool:
    """判断是否是源代码文件"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    return suffix in {".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go"}


class PostToolHook(BaseHook):
    """PostToolUse Hook - 工具执行后处理

    职责：
    1. 记录文件修改历史
    2. 检测测试文件修改
    3. （Phase 5）根据文件修改推荐测试
    """

    def __init__(self):
        self._modified_files: list[dict[str, Any]] = []
        self._memory_operations: list[dict[str, Any]] = []

    @property
    def hook_type(self) -> HookType:
        return HookType.POST_TOOL_USE

    @property
    def name(self) -> str:
        return "PostToolHook"

    @property
    def priority(self) -> int:
        # 中等优先级
        return 50

    def should_run(self, context: HookContext) -> bool:
        """只处理文件修改工具和 memory-anchor 工具"""
        tool_name = context.tool_name or ""

        # 提取实际工具名
        if tool_name.startswith("mcp__memory-anchor__"):
            actual_name = tool_name.replace("mcp__memory-anchor__", "")
            return actual_name in MEMORY_TOOLS

        return tool_name in FILE_MODIFY_TOOLS

    def execute(self, context: HookContext) -> HookResult:
        """执行 PostToolUse 处理"""
        tool_name = context.tool_name or ""
        tool_input = context.tool_input
        tool_output = context.tool_output

        # 处理文件修改
        if tool_name in FILE_MODIFY_TOOLS:
            return self._handle_file_modification(tool_name, tool_input, tool_output)

        # 处理 memory-anchor 操作
        if tool_name.startswith("mcp__memory-anchor__"):
            actual_name = tool_name.replace("mcp__memory-anchor__", "")
            return self._handle_memory_operation(actual_name, tool_input, tool_output)

        return HookResult.allow()

    def _handle_file_modification(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
    ) -> HookResult:
        """处理文件修改"""
        files = extract_modified_files(tool_name, tool_input)

        for file_path in files:
            record = {
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "file": file_path,
                "is_test": is_test_file(file_path),
                "is_source": is_source_file(file_path),
            }
            self._modified_files.append(record)
            logger.debug(f"File modified: {file_path}")

        # 检测源文件修改但没有对应测试修改
        source_files = [f for f in files if is_source_file(f) and not is_test_file(f)]

        if source_files:
            # Phase 5 会实现完整的测试建议逻辑
            # 目前只返回通知
            return HookResult.notify(
                message=f"Modified source files: {', '.join(source_files)}",
                reason="file_modification_detected",
            )

        return HookResult.allow()

    def _handle_memory_operation(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
    ) -> HookResult:
        """处理 memory-anchor 操作"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "input": tool_input,
            "success": tool_output is not None,
        }
        self._memory_operations.append(record)
        logger.debug(f"Memory operation: {tool_name}")

        return HookResult.notify(
            message=f"Memory operation: {tool_name}",
            reason="memory_operation_recorded",
        )

    def get_modified_files(self) -> list[dict[str, Any]]:
        """获取本次会话修改的文件列表"""
        return list(self._modified_files)

    def get_memory_operations(self) -> list[dict[str, Any]]:
        """获取本次会话的 memory 操作列表"""
        return list(self._memory_operations)

    def clear_history(self) -> None:
        """清除历史记录"""
        self._modified_files.clear()
        self._memory_operations.clear()

    def get_session_summary(self) -> dict[str, Any]:
        """生成会话摘要"""
        source_files = [
            f["file"]
            for f in self._modified_files
            if f["is_source"] and not f["is_test"]
        ]
        test_files = [f["file"] for f in self._modified_files if f["is_test"]]

        return {
            "total_modifications": len(self._modified_files),
            "source_files_modified": len(source_files),
            "test_files_modified": len(test_files),
            "memory_operations": len(self._memory_operations),
            "files": {
                "source": source_files,
                "test": test_files,
            },
        }


__all__ = [
    "PostToolHook",
    "extract_modified_files",
    "is_test_file",
    "is_source_file",
]
