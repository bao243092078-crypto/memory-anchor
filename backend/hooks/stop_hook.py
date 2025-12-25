#!/usr/bin/env python3
"""
Memory Anchor Stop Hook - 会话结束处理

Phase 3 增强版：
1. 生成会话摘要（Phase 1）
2. 整合 StateManager 项目级状态（Phase 2）
3. 自动写入 Memory Anchor（Phase 3）
4. 提取未完成任务（Phase 3）

用法：
    from backend.hooks import get_hook_registry, StopHook

    registry = get_hook_registry()
    registry.register(StopHook())

    # 会话结束时
    context = HookContext(hook_type=HookType.STOP, session_id="session-123")
    result = registry.execute_single(HookType.STOP, context)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.config import get_config
from backend.hooks.base import (
    BaseHook,
    HookContext,
    HookResult,
    HookType,
)

if TYPE_CHECKING:
    from backend.hooks.post_tool_hook import PostToolHook

logger = logging.getLogger(__name__)


# ============ TODO 提取器 ============

# TODO 匹配模式
TODO_PATTERNS = [
    # Python/JavaScript/TypeScript 风格
    r"#\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+?)(?:\n|$)",
    r"//\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+?)(?:\n|$)",
    # 多行注释风格
    r"\*\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+?)(?:\n|\*/)",
]

TODO_REGEX = re.compile("|".join(TODO_PATTERNS), re.IGNORECASE | re.MULTILINE)


def extract_todos_from_file(file_path: str) -> list[dict[str, Any]]:
    """从文件中提取 TODO 注释

    Args:
        file_path: 文件路径

    Returns:
        TODO 列表，每项包含 {type, content, file, line}
    """
    todos: list[dict[str, Any]] = []

    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return todos

        # 只处理代码文件
        if path.suffix.lower() not in {".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go"}:
            return todos

        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # 简单模式匹配
            for pattern in [
                r"#\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+)",
                r"//\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+)",
            ]:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    todo_type = match.group(1).upper()
                    todo_content = match.group(2).strip()
                    todos.append({
                        "type": todo_type,
                        "content": todo_content,
                        "file": file_path,
                        "line": line_num,
                    })
                    break

    except Exception as e:
        logger.warning(f"Failed to extract TODOs from {file_path}: {e}")

    return todos


def extract_todos_from_files(file_paths: list[str]) -> list[dict[str, Any]]:
    """从多个文件中提取 TODO 注释

    Args:
        file_paths: 文件路径列表

    Returns:
        合并的 TODO 列表
    """
    all_todos: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()  # (file, line) 去重

    for file_path in file_paths:
        todos = extract_todos_from_file(file_path)
        for todo in todos:
            key = (todo["file"], todo["line"])
            if key not in seen:
                seen.add(key)
                all_todos.append(todo)

    return all_todos


# ============ 会话摘要生成 ============


def generate_session_summary(
    session_id: str,
    modified_files: list[dict[str, Any]] | None = None,
    memory_operations: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """生成会话摘要

    Args:
        session_id: 会话 ID
        modified_files: 修改的文件列表（从 PostToolHook 获取）
        memory_operations: memory 操作列表（从 PostToolHook 获取）
        metadata: 额外元数据
        todos: 提取的 TODO 列表

    Returns:
        会话摘要字典
    """
    modified_files = modified_files or []
    memory_operations = memory_operations or []
    metadata = metadata or {}
    todos = todos or []

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
            "unfinished_tasks": len(todos),
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
        "unfinished_tasks": todos,
        "metadata": metadata,
    }

    return summary


def generate_memory_content(summary: dict[str, Any]) -> str:
    """生成写入 Memory Anchor 的内容

    Args:
        summary: 会话摘要

    Returns:
        格式化的记忆内容
    """
    stats = summary.get("statistics", {})
    files = summary.get("files", {})
    todos = summary.get("unfinished_tasks", [])

    parts = [
        f"会话 {summary.get('session_id', 'unknown')} 结束",
    ]

    # 文件修改统计
    if stats.get("source_files_modified", 0) > 0:
        parts.append(f"修改了 {stats['source_files_modified']} 个源文件")

    if stats.get("test_files_modified", 0) > 0:
        parts.append(f"修改了 {stats['test_files_modified']} 个测试文件")

    # 关键文件
    source_files = files.get("source", [])
    if source_files:
        key_files = source_files[:3]
        parts.append(f"关键文件: {', '.join(key_files)}")

    # 未完成任务
    if todos:
        todo_count = len(todos)
        parts.append(f"发现 {todo_count} 个未完成任务 (TODO/FIXME)")

    return "。".join(parts) + "。"


# ============ StopHook 实现 ============


class StopHook(BaseHook):
    """Stop Hook - 会话结束处理

    Phase 3 增强版职责：
    1. 收集会话统计信息
    2. 生成会话摘要
    3. 使用 StateManager 保存项目级状态
    4. 自动写入 Memory Anchor
    5. 提取未完成任务
    """

    def __init__(
        self,
        post_tool_hook: PostToolHook | None = None,
        auto_write_memory: bool = True,
        extract_todos: bool = True,
    ):
        """初始化 StopHook

        Args:
            post_tool_hook: PostToolHook 实例，用于获取文件修改历史
            auto_write_memory: 是否自动写入 Memory Anchor
            extract_todos: 是否提取未完成任务
        """
        self._post_tool_hook = post_tool_hook
        self._auto_write_memory = auto_write_memory
        self._extract_todos = extract_todos
        self._state_manager = None

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

    def set_post_tool_hook(self, post_tool_hook: PostToolHook) -> None:
        """设置 PostToolHook 引用"""
        self._post_tool_hook = post_tool_hook

    def _get_state_manager(self):
        """延迟获取 StateManager"""
        if self._state_manager is None:
            try:
                from backend.state.manager import get_state_manager
                self._state_manager = get_state_manager()
            except ImportError:
                logger.warning("StateManager not available, using fallback")
        return self._state_manager

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

        # 提取未完成任务
        todos: list[dict[str, Any]] = []
        if self._extract_todos and modified_files:
            source_files = [
                f["file"]
                for f in modified_files
                if f.get("is_source")
            ]
            todos = extract_todos_from_files(source_files)

        # 生成会话摘要
        summary = generate_session_summary(
            session_id=session_id,
            modified_files=modified_files,
            memory_operations=memory_operations,
            metadata=metadata,
            todos=todos,
        )

        # 使用 StateManager 保存状态（Phase 2 整合）
        state_manager = self._get_state_manager()
        archive_path = None

        if state_manager is not None:
            try:
                session_state = state_manager.get_current_session()
                if session_state is not None:
                    # 结束并归档会话
                    archive_path = state_manager.end_session(session_state)
                    logger.info(f"Session archived via StateManager: {archive_path}")
            except Exception as e:
                logger.warning(f"StateManager save failed: {e}")

        # 自动写入 Memory Anchor（Phase 3）
        memory_result = None
        if self._auto_write_memory:
            memory_result = self._write_to_memory_anchor(summary)

        # 格式化输出消息
        message = self._format_summary_message(summary, archive_path, memory_result)

        return HookResult.notify(
            message=message,
            reason=f"session_ended:{session_id}",
        )

    def _write_to_memory_anchor(self, summary: dict[str, Any]) -> dict[str, Any] | None:
        """写入 Memory Anchor

        Args:
            summary: 会话摘要

        Returns:
            写入结果，失败返回 None
        """
        try:
            from backend.core.memory_kernel import get_memory_kernel
            from backend.services.search import get_search_service

            kernel = get_memory_kernel(get_search_service())
            content = generate_memory_content(summary)

            result = kernel.add_memory(
                content=content,
                layer="event_log",  # 会话摘要存入事件日志层
                category="event",
                source="stop_hook",
                confidence=0.95,
            )

            logger.info(f"Session summary written to Memory Anchor: {result.get('id')}")
            return result

        except Exception as e:
            logger.error(f"Failed to write to Memory Anchor: {e}")
            return None

    def _format_summary_message(
        self,
        summary: dict[str, Any],
        archive_path: Path | None = None,
        memory_result: dict[str, Any] | None = None,
    ) -> str:
        """格式化摘要消息"""
        # 获取阈值配置
        config = get_config()
        max_files = config.summary_max_files
        max_todos = config.summary_max_todos
        max_todo_chars = config.todo_content_max_chars

        stats = summary.get("statistics", {})
        files = summary.get("files", {})
        todos = summary.get("unfinished_tasks", [])

        lines = [
            "📊 **会话摘要**",
            "",
            f"- 文件修改: {stats.get('total_file_modifications', 0)} 次",
            f"- 源文件: {stats.get('source_files_modified', 0)} 个",
            f"- 测试文件: {stats.get('test_files_modified', 0)} 个",
            f"- Memory 操作: {stats.get('memory_operations', 0)} 次",
        ]

        # 未完成任务
        if todos:
            lines.append(f"- 未完成任务: {len(todos)} 个")

        # 修改的源文件
        source_files = files.get("source", [])
        if source_files:
            lines.append("")
            lines.append("**修改的源文件**:")
            for f in source_files[:max_files]:
                lines.append(f"  - {f}")
            if len(source_files) > max_files:
                lines.append(f"  - ... 还有 {len(source_files) - max_files} 个")

        # 未完成任务列表
        if todos:
            lines.append("")
            lines.append("**未完成任务 (TODO/FIXME)**:")
            for todo in todos[:max_todos]:
                todo_type = todo.get("type", "TODO")
                content = todo.get("content", "")[:max_todo_chars]
                lines.append(f"  - [{todo_type}] {content}")
            if len(todos) > max_todos:
                lines.append(f"  - ... 还有 {len(todos) - max_todos} 个")

        # 状态保存信息
        lines.append("")
        if archive_path:
            lines.append(f"✅ 会话已归档: {archive_path.name}")
        if memory_result:
            lines.append("✅ 已写入 Memory Anchor")

        return "\n".join(lines)


__all__ = [
    "StopHook",
    "generate_session_summary",
    "generate_memory_content",
    "extract_todos_from_file",
    "extract_todos_from_files",
]
