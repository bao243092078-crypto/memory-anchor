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

确认短语：
- "确认删除" / "confirm delete"
- "我确认" / "I confirm"
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
HIGH_RISK_OPERATIONS = {
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
):
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


def gate_operation(
    tool_name: str,
    arguments: dict[str, Any],
    user_message: str | None = None,
) -> dict[str, Any]:
    """
    高风险操作门控

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
    risk_level, description = evaluate_risk(tool_name, arguments)

    # 无风险操作直接放行
    if risk_level is None:
        return {
            "allowed": True,
            "reason": None,
            "requires_confirmation": False,
            "confirmation_message": None,
        }

    # 类型断言：如果 risk_level 不为 None，description 也不为 None
    assert description is not None, "evaluate_risk should return both or neither"

    # 有风险操作，检查是否有确认
    has_confirmation = is_confirmation_present(user_message)

    if has_confirmation:
        # 有确认，放行但记录
        log_high_risk_attempt(
            tool_name, arguments, risk_level, description,
            blocked=False, reason="用户已确认"
        )
        return {
            "allowed": True,
            "reason": "用户已确认",
            "requires_confirmation": False,
            "confirmation_message": None,
        }

    # 无确认，阻止并要求确认
    confirmation_message = _build_confirmation_message(tool_name, arguments, risk_level, description)

    log_high_risk_attempt(
        tool_name, arguments, risk_level, description,
        blocked=True, reason="需要用户确认"
    )

    return {
        "allowed": False,
        "reason": f"高风险操作需要确认: {description}",
        "requires_confirmation": True,
        "confirmation_message": confirmation_message,
    }


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

        # 只处理 memory-anchor 相关工具
        # MCP 工具名格式: mcp__memory-anchor__<tool_name>
        if not (tool_name.startswith("mcp__memory-anchor__") or tool_name in HIGH_RISK_OPERATIONS):
            # 不是 memory-anchor 工具，直接放行
            print(json.dumps({}))
            sys.exit(0)

        # 提取实际工具名
        actual_tool_name = tool_name
        if tool_name.startswith("mcp__memory-anchor__"):
            actual_tool_name = tool_name.replace("mcp__memory-anchor__", "")

        # 评估风险
        result = gate_operation(actual_tool_name, tool_input)

        if result["allowed"]:
            # 允许执行
            print(json.dumps({}))
        else:
            # 阻止执行
            output = {
                "decision": "block",
                "reason": result["confirmation_message"] or result["reason"],
            }
            print(json.dumps(output))

    except Exception as e:
        # 出错时不阻止操作
        logger.error(f"Gating hook error: {e}")
        print(json.dumps({"systemMessage": f"Gating hook error: {e}"}))

    sys.exit(0)


if __name__ == "__main__":
    main()
