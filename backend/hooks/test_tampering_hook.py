#!/usr/bin/env python3
"""
Memory Anchor Test Tampering Hook - 测试篡改检测

Phase 6 实现：检测并拦截可疑的测试文件修改

检测模式：
1. 删除 assert 语句
2. 添加无理由的 @pytest.mark.skip
3. 修改断言的期望值（需确认）
4. 添加异常吞噬（except: pass）

使用方法：
    from backend.hooks import get_hook_registry, TestTamperingHook

    registry = get_hook_registry()
    registry.register(TestTamperingHook())
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

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
LOG_FILE = LOG_DIR / "test_tampering.log"

logger = logging.getLogger(__name__)

# 测试文件模式
TEST_FILE_PATTERNS = [
    r"(^|.*/)?test_[^/]+\.py$",      # test_*.py (with or without path)
    r".*_test\.py$",                  # *_test.py
    r"(^|.*/)?tests?/.*\.py$",        # tests/*.py, test/*.py (with or without path prefix)
    r".*\.test\.[jt]sx?$",            # *.test.js, *.test.ts, *.test.tsx
    r".*\.spec\.[jt]sx?$",            # *.spec.js, *.spec.ts
    r"(^|.*/)?__tests__/.*\.[jt]sx?$",  # __tests__/*.js (with or without path prefix)
]


class TamperingType(Enum):
    """篡改类型"""
    ASSERT_DELETION = "assert_deletion"
    SKIP_NO_REASON = "skip_no_reason"
    EXPECTED_VALUE_CHANGE = "expected_value_change"
    EXCEPTION_SWALLOWING = "exception_swallowing"
    BOUNDARY_TEST_DELETION = "boundary_test_deletion"


class TamperingSeverity(Enum):
    """严重程度"""
    CRITICAL = "critical"  # 阻止
    WARNING = "warning"    # 警告需确认
    INFO = "info"          # 仅通知

    def __lt__(self, other: "TamperingSeverity") -> bool:
        """Enable comparison for max() function."""
        order = {"info": 0, "warning": 1, "critical": 2}
        return order[self.value] < order[other.value]


@dataclass
class TamperingDetection:
    """篡改检测结果"""
    tampering_type: TamperingType
    severity: TamperingSeverity
    description: str
    old_content: str | None = None
    new_content: str | None = None


def is_test_file(file_path: str) -> bool:
    """判断是否是测试文件"""
    for pattern in TEST_FILE_PATTERNS:
        if re.match(pattern, file_path, re.IGNORECASE):
            return True
    return False


def detect_assert_deletion(old_string: str, new_string: str) -> TamperingDetection | None:
    """检测 assert 语句删除"""
    # 统计 assert 数量变化
    old_asserts = len(re.findall(r"^\s*assert\s+", old_string, re.MULTILINE))
    new_asserts = len(re.findall(r"^\s*assert\s+", new_string, re.MULTILINE))

    # 检查是否删除或注释掉了 assert
    if old_asserts > new_asserts:
        return TamperingDetection(
            tampering_type=TamperingType.ASSERT_DELETION,
            severity=TamperingSeverity.CRITICAL,
            description=f"删除了 {old_asserts - new_asserts} 个 assert 语句",
            old_content=old_string,
            new_content=new_string,
        )

    # 检查是否注释掉了 assert
    commented_asserts = len(re.findall(r"^\s*#\s*assert\s+", new_string, re.MULTILINE))
    if commented_asserts > 0 and "# assert" not in old_string:
        return TamperingDetection(
            tampering_type=TamperingType.ASSERT_DELETION,
            severity=TamperingSeverity.CRITICAL,
            description=f"注释掉了 {commented_asserts} 个 assert 语句",
            old_content=old_string,
            new_content=new_string,
        )

    return None


def detect_skip_no_reason(old_string: str, new_string: str) -> TamperingDetection | None:
    """检测无理由的 @pytest.mark.skip"""
    # 检查新增的 skip 装饰器
    skip_patterns = [
        r"@pytest\.mark\.skip\s*$",                    # @pytest.mark.skip
        r"@pytest\.mark\.skip\s*\(\s*\)",              # @pytest.mark.skip()
        r"@pytest\.mark\.skipif\s*\([^)]*\)\s*$",      # @pytest.mark.skipif(...) 无 reason
    ]

    for pattern in skip_patterns:
        # 在新内容中找到，但旧内容中没有
        new_matches = re.findall(pattern, new_string, re.MULTILINE)
        old_matches = re.findall(pattern, old_string, re.MULTILINE)

        if len(new_matches) > len(old_matches):
            # 检查是否有 reason
            has_reason = bool(re.search(r"@pytest\.mark\.skip\w*\s*\([^)]*reason\s*=", new_string))
            if not has_reason:
                return TamperingDetection(
                    tampering_type=TamperingType.SKIP_NO_REASON,
                    severity=TamperingSeverity.CRITICAL,
                    description="添加了无理由的 @pytest.mark.skip",
                    old_content=old_string,
                    new_content=new_string,
                )

    return None


def detect_expected_value_change(old_string: str, new_string: str) -> TamperingDetection | None:
    """检测断言期望值修改（需确认）"""
    # 简化检测：查找 assert x == Y 模式的变化
    assert_pattern = r"assert\s+.+\s*==\s*(.+)"

    old_expectations = re.findall(assert_pattern, old_string)
    new_expectations = re.findall(assert_pattern, new_string)

    # 如果期望值改变了（且不是新增断言）
    if old_expectations and new_expectations:
        for old_exp in old_expectations:
            for new_exp in new_expectations:
                # 同一个断言但值不同
                if old_exp.strip() != new_exp.strip():
                    # 排除变量名变化（只关注字面量变化）
                    if _is_literal_change(old_exp, new_exp):
                        return TamperingDetection(
                            tampering_type=TamperingType.EXPECTED_VALUE_CHANGE,
                            severity=TamperingSeverity.WARNING,
                            description=f"修改了断言期望值: {old_exp.strip()[:50]} → {new_exp.strip()[:50]}",
                            old_content=old_string,
                            new_content=new_string,
                        )

    return None


def _is_literal_change(old: str, new: str) -> bool:
    """判断是否是字面量变化（数字、字符串等）"""
    # 简化判断：如果两边都是数字或引号字符串
    old = old.strip()
    new = new.strip()

    # 数字变化
    try:
        float(old)
        float(new)
        return True
    except ValueError:
        pass

    # 字符串变化
    if (old.startswith(("'", '"')) and new.startswith(("'", '"'))):
        return True

    return False


def detect_exception_swallowing(old_string: str, new_string: str) -> TamperingDetection | None:
    """检测异常吞噬"""
    # 检测 except: pass 或 except Exception: pass
    swallow_patterns = [
        r"except\s*:\s*pass",
        r"except\s+\w+\s*:\s*pass",
        r"except\s+\w+\s+as\s+\w+:\s*pass",
    ]

    for pattern in swallow_patterns:
        new_matches = re.findall(pattern, new_string, re.MULTILINE)
        old_matches = re.findall(pattern, old_string, re.MULTILINE)

        if len(new_matches) > len(old_matches):
            return TamperingDetection(
                tampering_type=TamperingType.EXCEPTION_SWALLOWING,
                severity=TamperingSeverity.CRITICAL,
                description="添加了异常吞噬 (except: pass)",
                old_content=old_string,
                new_content=new_string,
            )

    return None


def detect_boundary_test_deletion(old_string: str, new_string: str) -> TamperingDetection | None:
    """检测边界测试删除"""
    boundary_keywords = ["boundary", "edge", "limit", "max", "min", "overflow", "underflow"]

    for keyword in boundary_keywords:
        # 检查包含边界关键词的测试函数是否被删除
        old_tests = re.findall(rf"def\s+test_[^(]*{keyword}[^(]*\(", old_string, re.IGNORECASE)
        new_tests = re.findall(rf"def\s+test_[^(]*{keyword}[^(]*\(", new_string, re.IGNORECASE)

        if len(old_tests) > len(new_tests):
            return TamperingDetection(
                tampering_type=TamperingType.BOUNDARY_TEST_DELETION,
                severity=TamperingSeverity.CRITICAL,
                description=f"删除了边界测试 (包含 '{keyword}')",
                old_content=old_string,
                new_content=new_string,
            )

    return None


def analyze_test_modification(old_string: str, new_string: str) -> list[TamperingDetection]:
    """分析测试文件修改，返回检测到的篡改"""
    detections: list[TamperingDetection] = []

    # 运行所有检测器
    detectors = [
        detect_assert_deletion,
        detect_skip_no_reason,
        detect_expected_value_change,
        detect_exception_swallowing,
        detect_boundary_test_deletion,
    ]

    for detector in detectors:
        result = detector(old_string, new_string)
        if result:
            detections.append(result)

    return detections


def log_tampering_attempt(
    file_path: str,
    detections: list[TamperingDetection],
    blocked: bool,
) -> None:
    """记录篡改尝试"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "file_path": file_path,
        "detections": [
            {
                "type": d.tampering_type.value,
                "severity": d.severity.value,
                "description": d.description,
            }
            for d in detections
        ],
        "blocked": blocked,
    }

    level = logging.WARNING if blocked else logging.INFO
    logger.log(level, f"Test modification: {file_path} - {len(detections)} issues - blocked={blocked}")

    # 追加到日志文件
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def _build_warning_message(
    file_path: str,
    detections: list[TamperingDetection],
) -> str:
    """构建警告消息"""
    severity_emoji = {
        TamperingSeverity.CRITICAL: "🔴",
        TamperingSeverity.WARNING: "🟡",
        TamperingSeverity.INFO: "ℹ️",
    }

    lines = [
        "⚠️ **测试修改警告**",
        "",
        f"文件: `{file_path}`",
        "",
        "检测到以下可疑修改:",
    ]

    for d in detections:
        emoji = severity_emoji.get(d.severity, "⚪")
        lines.append(f"- {emoji} {d.description}")

    lines.extend([
        "",
        "**测试是质量的守护者**。请确认：",
        "1. 这是有意为之吗？",
        "2. 是修复测试 Bug 还是掩盖代码 Bug？",
        "",
        "如果确定要继续，请说明理由后重新执行。",
    ])

    return "\n".join(lines)


class TestTamperingHook(BaseHook):
    """测试篡改检测 Hook

    检测可疑的测试文件修改：
    - 删除 assert 语句
    - 添加无理由的 skip
    - 修改期望值
    - 异常吞噬
    """

    @property
    def hook_type(self) -> HookType:
        return HookType.PRE_TOOL_USE

    @property
    def name(self) -> str:
        return "TestTamperingHook"

    @property
    def priority(self) -> int:
        # 中等优先级（在 GatingHook 之后）
        return 50

    def should_run(self, context: HookContext) -> bool:
        """只处理 Edit/Write 工具修改测试文件"""
        tool_name = context.tool_name or ""

        # 只处理文件修改工具
        if tool_name not in ("Edit", "Write", "MultiEdit"):
            return False

        # 获取文件路径
        file_path = context.tool_input.get("file_path", "")

        # 检查是否是测试文件
        return is_test_file(file_path)

    def execute(self, context: HookContext) -> HookResult:
        """执行测试篡改检测"""
        tool_name = context.tool_name or ""
        tool_input = context.tool_input
        file_path = tool_input.get("file_path", "")

        # 获取修改内容
        if tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
        elif tool_name == "Write":
            # Write 操作没有 old_string，需要特殊处理
            # 对于 Write，我们只检查新内容是否包含可疑模式
            old_string = ""
            new_string = tool_input.get("content", "")
        else:
            return HookResult.allow()

        # 分析修改
        detections = analyze_test_modification(old_string, new_string)

        if not detections:
            return HookResult.allow()

        # 判断最高严重程度
        max_severity = max(d.severity for d in detections)

        # 记录日志
        should_block = max_severity == TamperingSeverity.CRITICAL
        log_tampering_attempt(file_path, detections, blocked=should_block)

        # 构建消息
        message = _build_warning_message(file_path, detections)

        if should_block:
            return HookResult.block(
                reason=f"检测到可疑测试修改: {detections[0].description}",
                message=message,
            )
        else:
            # WARNING 级别：通知但不阻止
            return HookResult.notify(
                message=message,
                reason=f"测试修改警告: {detections[0].description}",
            )


# === Claude Code Hook 入口 ===


def main():
    """
    PreToolUse hook 入口点

    从 stdin 读取 JSON 输入，输出 JSON 到 stdout
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
            session_id=session_id,
        )

        # 使用 TestTamperingHook
        hook = TestTamperingHook()

        # 检查是否应该执行
        if not hook.should_run(context):
            print(json.dumps({}))
            sys.exit(0)

        # 执行检测
        result = hook.execute(context)

        if result.decision == HookDecision.BLOCK:
            output = {
                "decision": "block",
                "reason": result.message or result.reason,
            }
            print(json.dumps(output))
        elif result.decision == HookDecision.NOTIFY:
            # 通知但不阻止
            output = {
                "systemMessage": result.message,
            }
            print(json.dumps(output))
        else:
            print(json.dumps({}))

    except Exception as e:
        logger.error(f"Test tampering hook error: {e}")
        print(json.dumps({"systemMessage": f"Test tampering hook error: {e}"}))

    sys.exit(0)


__all__ = [
    "TestTamperingHook",
    "TamperingType",
    "TamperingSeverity",
    "TamperingDetection",
    "is_test_file",
    "analyze_test_modification",
]


if __name__ == "__main__":
    main()
