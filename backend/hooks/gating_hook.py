#!/usr/bin/env python3
"""
Memory Anchor Gating Hook - 高风险操作拦截

拦截以下高风险操作，要求用户明确确认：
1. delete_memory - 删除记忆
2. clear_* - 清除操作
3. constitution change with delete - 删除宪法层条目

使用方法：
1. 作为 Claude Code PreToolUse hook
2. 在 MCP Server 内部调用
3. 通过 HookRegistry 注册执行

确认短语：
- "确认删除" / "confirm delete"
- "我确认" / "I confirm"
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.hooks.base import (
    BaseHook,
    HookContext,
    HookDecision,
    HookResult,
    HookType,
)

# 配置日志
LOG_DIR = Path.home() / ".memory-anchor" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "gating.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)

# 高风险操作列表
HIGH_RISK_OPERATIONS: dict[str, tuple[str, str]] = {
    # MCP 工具名 -> (风险等级, 描述)
    "delete_memory": ("critical", "删除记忆"),
    "clear_active_context": ("high", "清除工作记忆"),
    # propose_constitution_change 已有三次审批，但 delete 类型额外警告
}

# 需要额外确认的 constitution change 类型
CONSTITUTION_DELETE_RISK = ("critical", "删除宪法层条目")

# 确认短语（大小写不敏感）
CONFIRMATION_PHRASES = [
    "确认删除",
    "confirm delete",
    "我确认",
    "i confirm",
    "确认执行",
    "confirm execute",
]


def is_confirmation_present(user_message: str | None) -> bool:
    """检查用户消息中是否包含确认短语"""
    if not user_message:
        return False

    message_lower = user_message.lower()
    return any(phrase.lower() in message_lower for phrase in CONFIRMATION_PHRASES)


def evaluate_risk(tool_name: str, arguments: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    评估操作风险

    Returns:
        (risk_level, description) 或 (None, None) 表示无风险
    """
    # 检查高风险工具
    if tool_name in HIGH_RISK_OPERATIONS:
        return HIGH_RISK_OPERATIONS[tool_name]

    # 检查 constitution change 的 delete 类型
    if tool_name == "propose_constitution_change":
        change_type = arguments.get("change_type", "")
        if change_type == "delete":
            return CONSTITUTION_DELETE_RISK

    return None, None


def log_high_risk_attempt(
    tool_name: str,
    arguments: dict[str, Any],
    risk_level: str,
    description: str,
    blocked: bool,
    reason: str | None = None,
) -> None:
    """记录高风险操作尝试"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "arguments": arguments,
        "risk_level": risk_level,
        "description": description,
        "blocked": blocked,
        "reason": reason,
    }

    if blocked:
        logger.warning(f"BLOCKED: {tool_name} - {description} - {reason}")
    else:
        logger.info(f"ALLOWED: {tool_name} - {description}")

    # 追加到日志文件
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def _build_confirmation_message(
    tool_name: str,
    arguments: dict[str, Any],
    risk_level: str,
    description: str,
) -> str:
    """构建确认消息"""
    risk_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
    }.get(risk_level, "⚪")

    lines = [
        f"{risk_emoji} **高风险操作警告**",
        "",
        f"您正在尝试执行: **{description}**",
        "",
        "操作详情:",
    ]

    # 显示关键参数
    for key, value in arguments.items():
        if value is not None:
            # 截断长内容
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:100] + "..."
            lines.append(f"- {key}: {str_value}")

    lines.extend([
        "",
        "**此操作可能不可逆。** 如果确定要执行，请回复包含以下任一确认短语的消息：",
        "- \"确认删除\"",
        "- \"我确认\"",
        "- \"confirm delete\"",
        "",
        "或取消此操作。",
    ])

    return "\n".join(lines)


class GatingHook(BaseHook):
    """高风险操作门控 Hook

    拦截高风险操作（删除记忆、清除上下文等），
    要求用户明确确认后才允许执行。
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.PRE_TOOL_USE

    @property
    def name(self) -> str:
        return "GatingHook"

    @property
    def priority(self) -> int:
        # 高优先级，确保第一个执行
        return 10

    def should_run(self, context: HookContext) -> bool:
        """只处理 memory-anchor 相关工具"""
        tool_name = context.tool_name or ""

        # MCP 工具名格式: mcp__memory-anchor__<tool_name>
        if tool_name.startswith("mcp__memory-anchor__"):
            return True

        # 直接使用工具名（内部调用）
        if tool_name in HIGH_RISK_OPERATIONS:
            return True

        # 检查 propose_constitution_change
        if tool_name == "propose_constitution_change":
            return True

        return False

    def _extract_tool_name(self, tool_name: str) -> str:
        """提取实际工具名"""
        if tool_name.startswith("mcp__memory-anchor__"):
            return tool_name.replace("mcp__memory-anchor__", "")
        return tool_name

    def execute(self, context: HookContext) -> HookResult:
        """执行门控检查"""
        tool_name = self._extract_tool_name(context.tool_name or "")
        arguments = context.tool_input
        user_message = context.user_message

        # 评估风险
        risk_level, description = evaluate_risk(tool_name, arguments)

        # 无风险操作直接放行
        if risk_level is None:
            return HookResult.allow()

        # 类型断言
        assert description is not None

        # 有风险操作，检查是否有确认
        has_confirmation = is_confirmation_present(user_message)

        if has_confirmation:
            # 有确认，放行但记录
            log_high_risk_attempt(
                tool_name, arguments, risk_level, description,
                blocked=False, reason="用户已确认"
            )
            return HookResult.allow(reason="用户已确认")

        # 无确认，阻止并要求确认
        confirmation_message = _build_confirmation_message(
            tool_name, arguments, risk_level, description
        )

        log_high_risk_attempt(
            tool_name, arguments, risk_level, description,
            blocked=True, reason="需要用户确认"
        )

        return HookResult.block(
            reason=f"高风险操作需要确认: {description}",
            message=confirmation_message
        )


# === 兼容旧 API ===

def gate_operation(
    tool_name: str,
    arguments: dict[str, Any],
    user_message: str | None = None,
) -> dict[str, Any]:
    """
    高风险操作门控（兼容旧 API）

    Args:
        tool_name: MCP 工具名
        arguments: 工具参数
        user_message: 用户最近的消息（用于检查确认短语）

    Returns:
        {
            "allowed": bool,
            "reason": str | None,
            "requires_confirmation": bool,
            "confirmation_message": str | None,
        }
    """
    # 使用新的 Hook 框架
    hook = GatingHook()
    context = HookContext(
        hook_type=HookType.PRE_TOOL_USE,
        tool_name=tool_name,
        tool_input=arguments,
        user_message=user_message
    )

    result = hook.execute(context)

    # 转换为旧 API 格式
    return {
        "allowed": result.decision != HookDecision.BLOCK,
        "reason": result.reason,
        "requires_confirmation": result.decision == HookDecision.BLOCK,
        "confirmation_message": result.message if result.decision == HookDecision.BLOCK else None,
    }


# === Claude Code Hook 入口 ===


def main():
    """
    PreToolUse hook 入口点

    从 stdin 读取 JSON 输入：
    {
        "tool_name": "...",
        "tool_input": {...},
        "session_id": "...",
        ...
    }

    输出 JSON 到 stdout：
    - 空 {} 表示允许
    - {"decision": "block", "reason": "..."} 表示阻止
    """
    try:
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id")

        # 创建上下文
        context = HookContext(
            hook_type=HookType.PRE_TOOL_USE,
            tool_name=tool_name,
            tool_input=tool_input,
            session_id=session_id
        )

        # 使用 GatingHook
        hook = GatingHook()

        # 检查是否应该执行
        if not hook.should_run(context):
            # 不是 memory-anchor 工具，直接放行
            print(json.dumps({}))
            sys.exit(0)

        # 执行门控检查
        result = hook.execute(context)

        if result.decision != HookDecision.BLOCK:
            # 允许执行
            print(json.dumps({}))
        else:
            # 阻止执行
            output = {
                "decision": "block",
                "reason": result.message or result.reason,
            }
            print(json.dumps(output))

    except Exception as e:
        # 出错时不阻止操作
        logger.error(f"Gating hook error: {e}")
        print(json.dumps({"systemMessage": f"Gating hook error: {e}"}))

    sys.exit(0)


if __name__ == "__main__":
    main()
