"""
Checkpoint Hook - 上下文保护钩子

在上下文压缩前（PreCompact）自动保存运行时状态：
- 端口和进程
- Git 状态（未提交变更、分支、stash）
- Todo 状态（进行中任务）
- Qdrant 服务状态

这确保压缩后可以恢复关键上下文。

用法：
    from backend.hooks import CheckpointHook, get_hook_registry

    registry = get_hook_registry()
    registry.register(CheckpointHook())
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from backend.hooks.base import BaseHook, HookContext, HookDecision, HookResult, HookType

# 添加 scripts 目录以导入 checkpoint.py 的功能
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

logger = logging.getLogger(__name__)


class CheckpointHook(BaseHook):
    """上下文保护 Hook

    在 PreCompact 时保存运行时状态到清单系统。
    这是 "清单革命" 上下文保护机制的核心。

    设计原则（来自三方 AI 头脑风暴）：
    - Plan skill = 战术层（单次任务）
    - Memory Anchor = 战略层（跨会话持久）
    - CheckpointHook = 桥梁（捕获运行时状态）
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.PRE_COMPACT

    @property
    def name(self) -> str:
        return "CheckpointHook"

    @property
    def priority(self) -> int:
        # 高优先级，确保在压缩前尽早保存
        return 10

    def execute(self, context: HookContext) -> HookResult:
        """执行上下文保护

        保存当前运行时状态，生成恢复提示。
        """
        try:
            # 获取项目 ID
            project_id = context.metadata.get("project_id")
            if not project_id:
                project_id = os.environ.get("MCP_MEMORY_PROJECT_ID", "default")

            # 导入 checkpoint 功能
            from checkpoint import (
                detect_git_status,
                detect_qdrant_status,
                detect_running_ports,
                detect_todo_status,
                get_checkpoint_file,
            )

            # 收集运行时状态
            ports = detect_running_ports()
            qdrant = detect_qdrant_status()
            git_status = detect_git_status()
            todo_status = detect_todo_status()

            checkpoint = {
                "timestamp": datetime.now().isoformat(),
                "project_id": project_id,
                "trigger": "PreCompact",
                "ports": ports,
                "qdrant": qdrant,
                "git_status": git_status,
                "todo_status": todo_status,
            }

            # 生成恢复提示
            recovery_hints = self._generate_recovery_hints(checkpoint)
            checkpoint["recovery_hints"] = recovery_hints

            # 保存到本地文件
            checkpoint_file = get_checkpoint_file(project_id)
            try:
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(checkpoint, f, ensure_ascii=False, indent=2)
                checkpoint["checkpoint_file"] = str(checkpoint_file)
            except OSError as e:
                logger.warning(f"Failed to save checkpoint file: {e}")

            # 生成通知消息
            summary_parts = []
            if ports:
                summary_parts.append(f"{len(ports)} ports")
            if git_status.get("uncommitted_changes"):
                summary_parts.append(f"{len(git_status['uncommitted_changes'])} uncommitted")
            if todo_status.get("in_progress"):
                summary_parts.append(f"{len(todo_status['in_progress'])} todos")

            if summary_parts:
                message = f"[Checkpoint] Saved: {', '.join(summary_parts)}"
            else:
                message = "[Checkpoint] Saved (no active state)"

            # 如果有重要状态需要恢复，创建清单项
            if self._has_important_state(checkpoint):
                self._create_checklist_item(project_id, checkpoint)

            logger.info(message)

            return HookResult.notify(
                message=message,
                reason="PreCompact checkpoint saved",
            )

        except ImportError as e:
            logger.error(f"Failed to import checkpoint module: {e}")
            return HookResult.allow(reason=f"Checkpoint unavailable: {e}")
        except Exception as e:
            logger.error(f"Checkpoint failed: {e}")
            return HookResult.allow(reason=f"Checkpoint error: {e}")

    def _generate_recovery_hints(self, checkpoint: dict) -> list[str]:
        """生成恢复提示"""
        hints = []

        # Git 相关
        git_status = checkpoint.get("git_status", {})
        uncommitted = git_status.get("uncommitted_changes", [])
        if uncommitted:
            modified = [c for c in uncommitted if c.get("status") in ("M", "MM")]
            if modified:
                hints.append(f"Git: {len(modified)} files modified")

        if git_status.get("has_stash"):
            hints.append("Git: stash pending (run `git stash pop`)")

        ahead = git_status.get("ahead_behind", {}).get("ahead", 0)
        if ahead > 0:
            hints.append(f"Git: {ahead} commits to push")

        # Todo 相关
        todo_status = checkpoint.get("todo_status", {})
        in_progress = todo_status.get("in_progress", [])
        if in_progress:
            for todo in in_progress[:3]:
                hints.append(f"Todo: {todo.get('content', '')[:50]}")

        # 端口相关
        ports = checkpoint.get("ports", [])
        if ports:
            port_list = ", ".join([f":{p['port']}" for p in ports])
            hints.append(f"Ports: {port_list} listening")

        # Qdrant 相关
        qdrant = checkpoint.get("qdrant", {})
        if qdrant.get("status") == "offline":
            hints.append("Qdrant: OFFLINE (memory limited)")

        return hints

    def _has_important_state(self, checkpoint: dict) -> bool:
        """判断是否有重要状态需要恢复"""
        # 有进行中的任务
        if checkpoint.get("todo_status", {}).get("in_progress"):
            return True

        # 有未提交的变更
        if checkpoint.get("git_status", {}).get("uncommitted_changes"):
            return True

        # 有运行中的端口
        if checkpoint.get("ports"):
            return True

        return False

    def _create_checklist_item(self, project_id: str, checkpoint: dict) -> None:
        """创建清单项提醒恢复上下文"""
        try:
            from backend.models.checklist import (
                ChecklistItemCreate,
                ChecklistPriority,
                ChecklistScope,
            )
            from backend.services.checklist_service import ChecklistService

            # 构建综合恢复提示
            content_parts = []

            ports = checkpoint.get("ports", [])
            if ports:
                port_list = ", ".join([f":{p['port']}" for p in ports])
                content_parts.append(f"端口 {port_list} 正在运行")

            git_status = checkpoint.get("git_status", {})
            uncommitted = git_status.get("uncommitted_changes", [])
            if uncommitted:
                content_parts.append(f"{len(uncommitted)} 个未提交变更")

            todo_status = checkpoint.get("todo_status", {})
            in_progress = todo_status.get("in_progress", [])
            if in_progress:
                content_parts.append(f"{len(in_progress)} 个进行中任务")

            if git_status.get("has_stash"):
                content_parts.append("有 stash 未恢复")

            content = "[PreCompact] " + "；".join(content_parts)

            service = ChecklistService()
            item = service.create_item(
                project_id=project_id,
                request=ChecklistItemCreate(
                    content=content,
                    scope=ChecklistScope.PROJECT,
                    priority=ChecklistPriority.HIGH,
                    tags=[
                        "@runtime",
                        "@pre-compact",
                        f"session-{datetime.now().strftime('%Y%m%d')}",
                    ],
                ),
            )
            logger.info(f"Created checklist item: {item.ma_ref()}")

        except Exception as e:
            logger.warning(f"Failed to create checklist item: {e}")


__all__ = ["CheckpointHook"]
