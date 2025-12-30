"""
test_safety_filter.py - SafetyFilter 测试 (v3.0)

测试覆盖：
- PII 检测（邮箱、电话、身份证、信用卡、IP、API密钥）
- PII 脱敏
- 敏感词检测
- 长度限制
- 自定义模式
- 环境变量配置
- 与 MemoryKernel 集成
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from backend.core.safety_filter import (
    FilterAction,
    FilterResult,
    PIIType,
    SafetyConfig,
    SafetyFilter,
    get_safety_filter,
    reset_safety_filter,
    check_content_safety,
    is_content_safe,
)


class TestSafetyConfig:
    """SafetyConfig 测试"""

    def test_default_values(self):
        """测试默认值"""
        config = SafetyConfig()
        assert config.enabled is True
        assert config.max_length == 2000
        assert config.pii_detection is True
        assert config.pii_action == FilterAction.REDACT
        assert config.sensitive_word_action == FilterAction.WARN
        assert config.redact_placeholder == "[REDACTED]"

    def test_from_env(self):
        """测试从环境变量加载"""
        with patch.dict(os.environ, {
            "MA_SAFETY_ENABLED": "false",
            "MA_SAFETY_MAX_LENGTH": "5000",
            "MA_SAFETY_PII_ACTION": "block",
            "MA_SAFETY_SENSITIVE_WORDS": "password,secret,token",
        }):
            config = SafetyConfig.from_env()
            assert config.enabled is False
            assert config.max_length == 5000
            assert config.pii_action == FilterAction.BLOCK
            assert "password" in config.sensitive_words
            assert "secret" in config.sensitive_words
            assert "token" in config.sensitive_words


class TestFilterResult:
    """FilterResult 测试"""

    def test_is_blocked(self):
        """测试阻止判断"""
        result = FilterResult(
            action=FilterAction.BLOCK,
            original_content="test",
            filtered_content="test",
            blocked_reasons=["Content too long"],
        )
        assert result.is_blocked is True

    def test_is_not_blocked(self):
        """测试未阻止"""
        result = FilterResult(
            action=FilterAction.ALLOW,
            original_content="test",
            filtered_content="test",
        )
        assert result.is_blocked is False

    def test_is_modified(self):
        """测试内容修改判断"""
        result = FilterResult(
            action=FilterAction.REDACT,
            original_content="email: test@example.com",
            filtered_content="email: [REDACTED]",
        )
        assert result.is_modified is True

    def test_to_dict(self):
        """测试字典转换"""
        result = FilterResult(
            action=FilterAction.WARN,
            original_content="test",
            filtered_content="test",
            warnings=["Sensitive word detected"],
        )
        d = result.to_dict()
        assert d["action"] == "warn"
        assert d["is_blocked"] is False
        assert d["is_modified"] is False
        assert "Sensitive word detected" in d["warnings"]


class TestSafetyFilterPII:
    """SafetyFilter PII 检测测试"""

    @pytest.fixture
    def filter(self):
        """创建测试用过滤器"""
        config = SafetyConfig(
            enabled=True,
            pii_detection=True,
            pii_action=FilterAction.REDACT,
        )
        return SafetyFilter(config)

    def test_detect_email(self, filter):
        """测试邮箱检测"""
        result = filter.check("我的邮箱是 test@example.com")
        assert PIIType.EMAIL.value in result.pii_detected
        assert "[REDACTED]" in result.filtered_content
        assert "test@example.com" not in result.filtered_content

    def test_detect_phone_cn(self, filter):
        """测试中国手机号检测"""
        result = filter.check("联系电话：13812345678")
        assert PIIType.PHONE_CN.value in result.pii_detected
        assert "[REDACTED]" in result.filtered_content

    def test_detect_phone_us(self, filter):
        """测试美国电话检测"""
        result = filter.check("Call me at 555-123-4567")
        assert PIIType.PHONE_US.value in result.pii_detected

    def test_detect_id_card_cn(self, filter):
        """测试中国身份证检测"""
        result = filter.check("身份证号：110101199001011234")
        assert PIIType.ID_CARD_CN.value in result.pii_detected

    def test_detect_credit_card(self, filter):
        """测试信用卡号检测"""
        result = filter.check("信用卡：4111-1111-1111-1111")
        assert PIIType.CREDIT_CARD.value in result.pii_detected

    def test_detect_ip_address(self, filter):
        """测试 IP 地址检测"""
        result = filter.check("服务器 IP：192.168.1.100")
        assert PIIType.IP_ADDRESS.value in result.pii_detected

    def test_detect_api_key(self, filter):
        """测试 API 密钥检测"""
        result = filter.check("API Key: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert PIIType.API_KEY.value in result.pii_detected

    def test_multiple_pii(self, filter):
        """测试多种 PII 同时检测"""
        result = filter.check(
            "邮箱: test@example.com, 电话: 13812345678, IP: 10.0.0.1"
        )
        assert len(result.pii_detected) >= 3
        assert result.filtered_content.count("[REDACTED]") >= 3

    def test_no_pii(self, filter):
        """测试无 PII 内容"""
        result = filter.check("这是一条普通的记忆内容，没有敏感信息")
        assert len(result.pii_detected) == 0
        assert result.action == FilterAction.ALLOW


class TestSafetyFilterSensitiveWords:
    """SafetyFilter 敏感词检测测试"""

    @pytest.fixture
    def filter(self):
        """创建带敏感词的过滤器"""
        config = SafetyConfig(
            enabled=True,
            sensitive_words={"password", "密码", "secret"},
            sensitive_word_action=FilterAction.WARN,
        )
        return SafetyFilter(config)

    def test_detect_sensitive_word_en(self, filter):
        """测试英文敏感词"""
        result = filter.check("The password is 123456")
        assert "password" in result.sensitive_words_detected
        assert result.action == FilterAction.WARN

    def test_detect_sensitive_word_cn(self, filter):
        """测试中文敏感词"""
        result = filter.check("我的密码忘记了")
        assert "密码" in result.sensitive_words_detected

    def test_no_sensitive_words(self, filter):
        """测试无敏感词"""
        result = filter.check("这是一条普通内容")
        assert len(result.sensitive_words_detected) == 0


class TestSafetyFilterLengthLimit:
    """SafetyFilter 长度限制测试"""

    def test_content_within_limit(self):
        """测试内容在限制内"""
        config = SafetyConfig(max_length=100)
        filter = SafetyFilter(config)
        result = filter.check("短内容")
        assert result.action != FilterAction.BLOCK

    def test_content_exceeds_limit(self):
        """测试内容超过限制"""
        config = SafetyConfig(max_length=10)
        filter = SafetyFilter(config)
        result = filter.check("这是一条超过十个字符的内容")
        assert result.is_blocked is True
        assert any("max length" in r for r in result.blocked_reasons)


class TestSafetyFilterCustomPatterns:
    """SafetyFilter 自定义模式测试"""

    def test_add_custom_pattern(self):
        """测试添加自定义模式"""
        filter = SafetyFilter()
        filter.add_custom_pattern("test_pattern", r"SECRET_\d+")
        result = filter.check("Code: SECRET_12345")
        assert "test_pattern" in result.warnings[0] if result.warnings else False


class TestSafetyFilterDisabled:
    """SafetyFilter 禁用测试"""

    def test_disabled_filter(self):
        """测试禁用过滤器"""
        config = SafetyConfig(enabled=False)
        filter = SafetyFilter(config)
        result = filter.check("邮箱: test@example.com, 密码: 123456")
        assert result.action == FilterAction.ALLOW
        assert result.is_modified is False


class TestSafetyFilterBlockAction:
    """SafetyFilter 阻止动作测试"""

    def test_pii_block_action(self):
        """测试 PII 阻止动作"""
        config = SafetyConfig(
            pii_detection=True,
            pii_action=FilterAction.BLOCK,
        )
        filter = SafetyFilter(config)
        result = filter.check("邮箱: test@example.com")
        assert result.is_blocked is True
        assert "PII detected" in result.blocked_reasons[0]


class TestSafetyFilterEmptyContent:
    """SafetyFilter 空内容测试"""

    def test_empty_string(self):
        """测试空字符串"""
        filter = SafetyFilter()
        result = filter.check("")
        assert result.action == FilterAction.ALLOW

    def test_none_like(self):
        """测试空白内容"""
        filter = SafetyFilter()
        result = filter.check("   ")
        assert result.action == FilterAction.ALLOW


class TestModuleFunctions:
    """模块级函数测试"""

    def test_get_safety_filter_singleton(self):
        """测试单例模式"""
        reset_safety_filter()
        f1 = get_safety_filter()
        f2 = get_safety_filter()
        assert f1 is f2

    def test_reset_safety_filter(self):
        """测试重置单例"""
        reset_safety_filter()
        f1 = get_safety_filter()
        reset_safety_filter()
        f2 = get_safety_filter()
        assert f1 is not f2

    def test_check_content_safety(self):
        """测试便捷函数"""
        reset_safety_filter()
        result = check_content_safety("test content")
        assert isinstance(result, FilterResult)

    def test_is_content_safe(self):
        """测试快速检查函数"""
        reset_safety_filter()
        assert is_content_safe("normal content") is True


class TestSafetyFilterIntegration:
    """SafetyFilter 与 MemoryKernel 集成测试"""

    def test_kernel_with_safety_filter(self):
        """测试 MemoryKernel 集成"""
        from backend.core.memory_kernel import MemoryKernel

        # Mock search service
        mock_search = MagicMock()
        mock_search.index_note = MagicMock(return_value=True)

        # 创建带安全过滤器的内核
        config = SafetyConfig(
            pii_detection=True,
            pii_action=FilterAction.BLOCK,
        )
        safety_filter = SafetyFilter(config)
        kernel = MemoryKernel(mock_search, safety_filter=safety_filter)

        # 测试阻止含 PII 的内容
        result = kernel.add_memory(
            content="我的邮箱是 test@example.com",
            layer="verified_fact",
        )
        assert result["status"] == "blocked_by_safety_filter"
        assert "email" in result["pii_detected"]
        # index_note 不应被调用
        mock_search.index_note.assert_not_called()

    def test_kernel_without_safety_filter(self):
        """测试无安全过滤器的 MemoryKernel"""
        from backend.core.memory_kernel import MemoryKernel

        mock_search = MagicMock()
        mock_search.index_note = MagicMock(return_value=True)

        kernel = MemoryKernel(mock_search)

        # 无过滤器时正常写入
        result = kernel.add_memory(
            content="我的邮箱是 test@example.com",
            layer="verified_fact",
        )
        assert result["status"] == "saved"
        mock_search.index_note.assert_called_once()

    def test_kernel_redact_content(self):
        """测试内容脱敏后写入"""
        from backend.core.memory_kernel import MemoryKernel

        mock_search = MagicMock()
        mock_search.index_note = MagicMock(return_value=True)

        # 使用 REDACT 动作
        config = SafetyConfig(
            pii_detection=True,
            pii_action=FilterAction.REDACT,
        )
        safety_filter = SafetyFilter(config)
        kernel = MemoryKernel(mock_search, safety_filter=safety_filter)

        result = kernel.add_memory(
            content="联系我: test@example.com",
            layer="verified_fact",
        )
        assert result["status"] == "saved"

        # 检查写入的内容是否被脱敏
        call_args = mock_search.index_note.call_args
        indexed_content = call_args.kwargs.get("content")
        assert "[REDACTED]" in indexed_content
        assert "test@example.com" not in indexed_content
