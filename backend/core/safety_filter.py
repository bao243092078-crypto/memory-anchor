"""
SafetyFilter - 记忆安全过滤器 (v3.0)

在记忆写入前进行安全检查，防止敏感信息泄露。

设计原则：
1. 隐私优先 - 默认启用 PII 检测
2. 可配置 - 敏感词表可自定义
3. 优雅降级 - 过滤失败不阻塞写入，但会记录警告
4. 可审计 - 提供过滤报告

基于四方 AI 头脑风暴结论：
- Zep 的隐私保护机制（PII 检测 + 脱敏）
- 极简理念：默认规则够用，高级用户可扩展

参考：
- Zep 论文 arXiv:2501.13956 (隐私保护)
- GDPR/CCPA 合规要求
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger(__name__)


class FilterAction(str, Enum):
    """过滤动作"""
    ALLOW = "allow"       # 允许通过
    WARN = "warn"         # 警告但允许
    REDACT = "redact"     # 脱敏后允许
    BLOCK = "block"       # 阻止写入


class PIIType(str, Enum):
    """PII 类型"""
    EMAIL = "email"
    PHONE_CN = "phone_cn"           # 中国手机号
    PHONE_US = "phone_us"           # 美国电话
    ID_CARD_CN = "id_card_cn"       # 中国身份证
    CREDIT_CARD = "credit_card"     # 信用卡号
    IP_ADDRESS = "ip_address"       # IP 地址
    API_KEY = "api_key"             # API 密钥模式


@dataclass
class FilterResult:
    """过滤结果"""
    action: FilterAction
    original_content: str
    filtered_content: str
    warnings: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    pii_detected: List[str] = field(default_factory=list)
    sensitive_words_detected: List[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        """是否被阻止"""
        return self.action == FilterAction.BLOCK

    @property
    def is_modified(self) -> bool:
        """内容是否被修改"""
        return self.original_content != self.filtered_content

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "action": self.action.value,
            "is_blocked": self.is_blocked,
            "is_modified": self.is_modified,
            "warnings": self.warnings,
            "blocked_reasons": self.blocked_reasons,
            "pii_detected": self.pii_detected,
            "sensitive_words_detected": self.sensitive_words_detected,
        }


@dataclass
class SafetyConfig:
    """
    安全过滤配置

    可通过环境变量覆盖：
    - MA_SAFETY_ENABLED: 是否启用过滤 (true/false)
    - MA_SAFETY_MAX_LENGTH: 最大内容长度
    - MA_SAFETY_PII_ACTION: PII 检测动作 (warn/redact/block)
    - MA_SAFETY_SENSITIVE_WORDS: 敏感词列表（逗号分隔）
    """
    enabled: bool = True                    # 是否启用过滤
    max_length: int = 2000                  # 最大内容长度（字符）
    pii_detection: bool = True              # 是否检测 PII
    pii_action: FilterAction = FilterAction.REDACT  # PII 检测动作
    sensitive_word_action: FilterAction = FilterAction.WARN  # 敏感词动作
    sensitive_words: Set[str] = field(default_factory=set)  # 敏感词列表
    redact_placeholder: str = "[REDACTED]"  # 脱敏占位符

    @classmethod
    def from_env(cls) -> "SafetyConfig":
        """从环境变量加载配置"""
        enabled = os.getenv("MA_SAFETY_ENABLED", "true").lower() == "true"
        max_length = int(os.getenv("MA_SAFETY_MAX_LENGTH", "2000"))

        pii_action_str = os.getenv("MA_SAFETY_PII_ACTION", "redact").lower()
        pii_action = FilterAction(pii_action_str) if pii_action_str in [a.value for a in FilterAction] else FilterAction.REDACT

        sensitive_word_str = os.getenv("MA_SAFETY_SENSITIVE_WORDS", "")
        sensitive_words = set(w.strip() for w in sensitive_word_str.split(",") if w.strip())

        return cls(
            enabled=enabled,
            max_length=max_length,
            pii_action=pii_action,
            sensitive_words=sensitive_words,
        )


class SafetyFilter:
    """
    记忆安全过滤器

    职责：
    1. PII 检测和脱敏
    2. 敏感词检测
    3. 长度限制
    4. 生成过滤报告

    使用示例：
    ```python
    filter = SafetyFilter()

    # 检查内容
    result = filter.check("我的邮箱是 test@example.com")

    if result.is_blocked:
        print("内容被阻止:", result.blocked_reasons)
    else:
        safe_content = result.filtered_content  # 脱敏后的内容
    ```
    """

    # PII 正则表达式
    PII_PATTERNS: Dict[PIIType, Pattern] = {
        # 邮箱
        PIIType.EMAIL: re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ),
        # 中国手机号 (1开头的11位数字)
        PIIType.PHONE_CN: re.compile(
            r'\b1[3-9]\d{9}\b'
        ),
        # 美国电话 (xxx-xxx-xxxx 或 (xxx) xxx-xxxx)
        PIIType.PHONE_US: re.compile(
            r'\b(?:\(\d{3}\)\s?|\d{3}[-.])\d{3}[-.]?\d{4}\b'
        ),
        # 中国身份证号 (18位)
        PIIType.ID_CARD_CN: re.compile(
            r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b'
        ),
        # 信用卡号 (16位数字，可能有空格或连字符)
        PIIType.CREDIT_CARD: re.compile(
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        ),
        # IP 地址
        PIIType.IP_ADDRESS: re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ),
        # API 密钥模式 (常见格式: sk-xxx, api_xxx, key_xxx 等)
        PIIType.API_KEY: re.compile(
            r'\b(?:sk-|api[_-]|key[_-]|secret[_-]|token[_-]|auth[_-])[A-Za-z0-9_-]{20,}\b',
            re.IGNORECASE
        ),
    }

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        初始化安全过滤器

        Args:
            config: 安全配置，默认从环境变量加载
        """
        self.config = config or SafetyConfig.from_env()
        self._custom_patterns: Dict[str, Pattern] = {}

    def add_sensitive_word(self, word: str) -> None:
        """添加敏感词"""
        self.config.sensitive_words.add(word.lower())

    def add_sensitive_words(self, words: List[str]) -> None:
        """批量添加敏感词"""
        for word in words:
            self.add_sensitive_word(word)

    def add_custom_pattern(self, name: str, pattern: str) -> None:
        """添加自定义检测模式"""
        self._custom_patterns[name] = re.compile(pattern)

    def check(self, content: str) -> FilterResult:
        """
        检查内容安全性

        Args:
            content: 要检查的内容

        Returns:
            FilterResult 对象
        """
        if not self.config.enabled:
            return FilterResult(
                action=FilterAction.ALLOW,
                original_content=content,
                filtered_content=content,
            )

        if not content:
            return FilterResult(
                action=FilterAction.ALLOW,
                original_content="",
                filtered_content="",
            )

        warnings: List[str] = []
        blocked_reasons: List[str] = []
        pii_detected: List[str] = []
        sensitive_words_detected: List[str] = []
        filtered_content = content

        # 1. 长度检查
        if len(content) > self.config.max_length:
            blocked_reasons.append(
                f"Content exceeds max length ({len(content)} > {self.config.max_length})"
            )

        # 2. PII 检测
        if self.config.pii_detection:
            filtered_content, pii_found = self._detect_and_redact_pii(
                filtered_content
            )
            pii_detected.extend(pii_found)

            if pii_found:
                if self.config.pii_action == FilterAction.BLOCK:
                    blocked_reasons.append(f"PII detected: {', '.join(pii_found)}")
                elif self.config.pii_action == FilterAction.WARN:
                    warnings.append(f"PII detected: {', '.join(pii_found)}")
                # REDACT 时已经脱敏，不需要额外处理

        # 3. 敏感词检测
        sensitive_found = self._detect_sensitive_words(content)
        sensitive_words_detected.extend(sensitive_found)

        if sensitive_found:
            if self.config.sensitive_word_action == FilterAction.BLOCK:
                blocked_reasons.append(
                    f"Sensitive words detected: {', '.join(sensitive_found)}"
                )
            elif self.config.sensitive_word_action == FilterAction.WARN:
                warnings.append(
                    f"Sensitive words detected: {', '.join(sensitive_found)}"
                )

        # 4. 自定义模式检测
        custom_matches = self._check_custom_patterns(content)
        if custom_matches:
            warnings.append(f"Custom patterns matched: {', '.join(custom_matches)}")

        # 确定最终动作
        if blocked_reasons:
            action = FilterAction.BLOCK
        elif filtered_content != content:
            action = FilterAction.REDACT
        elif warnings:
            action = FilterAction.WARN
        else:
            action = FilterAction.ALLOW

        return FilterResult(
            action=action,
            original_content=content,
            filtered_content=filtered_content,
            warnings=warnings,
            blocked_reasons=blocked_reasons,
            pii_detected=pii_detected,
            sensitive_words_detected=sensitive_words_detected,
        )

    def _detect_and_redact_pii(self, content: str) -> Tuple[str, List[str]]:
        """
        检测并脱敏 PII

        Returns:
            (脱敏后的内容, 检测到的 PII 类型列表)
        """
        pii_found: List[str] = []
        redacted_content = content

        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(content)
            if matches:
                pii_found.append(pii_type.value)
                if self.config.pii_action == FilterAction.REDACT:
                    redacted_content = pattern.sub(
                        self.config.redact_placeholder,
                        redacted_content
                    )
                    logger.info(f"Redacted {len(matches)} {pii_type.value} instance(s)")

        return redacted_content, pii_found

    def _detect_sensitive_words(self, content: str) -> List[str]:
        """检测敏感词"""
        if not self.config.sensitive_words:
            return []

        content_lower = content.lower()
        found: List[str] = []

        for word in self.config.sensitive_words:
            if word in content_lower:
                found.append(word)

        return found

    def _check_custom_patterns(self, content: str) -> List[str]:
        """检查自定义模式"""
        matched: List[str] = []

        for name, pattern in self._custom_patterns.items():
            if pattern.search(content):
                matched.append(name)

        return matched

    def is_safe(self, content: str) -> bool:
        """
        快速检查内容是否安全

        Returns:
            True if content passes all checks
        """
        result = self.check(content)
        return not result.is_blocked


# ===== 模块级便捷函数 =====

_default_filter: Optional[SafetyFilter] = None


def get_safety_filter() -> SafetyFilter:
    """获取默认的安全过滤器单例"""
    global _default_filter
    if _default_filter is None:
        _default_filter = SafetyFilter()
    return _default_filter


def reset_safety_filter() -> None:
    """重置默认安全过滤器（用于测试）"""
    global _default_filter
    _default_filter = None


def check_content_safety(content: str) -> FilterResult:
    """便捷函数：检查内容安全性"""
    return get_safety_filter().check(content)


def is_content_safe(content: str) -> bool:
    """便捷函数：快速检查内容是否安全"""
    return get_safety_filter().is_safe(content)
