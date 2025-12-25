"""
Tests for Memory Refiner service.

Tests the CoDA-inspired memory refinement functionality:
- Observation Masking strategy
- LLM Provider abstraction
- Memory compression and summarization
"""

import pytest

from backend.services.llm_provider import (
    AnthropicProvider,
    LocalFallbackProvider,
    LLMProvider,
    LLMResponse,
    OpenAIProvider,
    get_llm_provider,
    reset_llm_provider,
)
from backend.services.memory_refiner import (
    MemoryRefiner,
    RefineResult,
    get_memory_refiner,
    reset_memory_refiner,
)


class TestLLMProvider:
    """Tests for LLM Provider abstraction layer."""

    def test_local_fallback_always_available(self):
        """LocalFallbackProvider should always be available."""
        provider = LocalFallbackProvider()
        assert provider.is_available is True
        assert provider.name == "local_fallback"

    @pytest.mark.asyncio
    async def test_local_fallback_simple_compress(self):
        """LocalFallbackProvider should compress text when too long."""
        provider = LocalFallbackProvider()

        # Short text should pass through unchanged
        short_text = "Hello, world!"
        result = await provider.complete(short_text, max_tokens=100)
        assert result.success is True
        assert result.model == "local_fallback"

    @pytest.mark.asyncio
    async def test_local_fallback_long_text_compression(self):
        """LocalFallbackProvider should compress long text."""
        provider = LocalFallbackProvider()

        # Create long text
        long_text = "A" * 5000
        result = await provider.complete(long_text, max_tokens=100)

        assert result.success is True
        # Result should be shorter than input
        assert len(result.content) < len(long_text)
        # Should contain truncation marker
        assert "中间内容已省略" in result.content

    def test_anthropic_provider_unavailable_without_key(self, monkeypatch):
        """AnthropicProvider should be unavailable without API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = AnthropicProvider()
        # Without key, provider is not available
        assert provider.api_key is None or not provider.is_available

    def test_openai_provider_unavailable_without_key(self, monkeypatch):
        """OpenAIProvider should be unavailable without API key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIProvider()
        assert provider.api_key is None or not provider.is_available

    def test_get_llm_provider_falls_back_to_local(self, monkeypatch):
        """get_llm_provider should fall back to local without API keys."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)

        reset_llm_provider()
        provider = get_llm_provider()

        assert provider.name == "local_fallback"
        assert provider.is_available is True

    def test_get_llm_provider_respects_env_var(self, monkeypatch):
        """get_llm_provider should respect LLM_PROVIDER env var."""
        monkeypatch.setenv("LLM_PROVIDER", "local")
        reset_llm_provider()

        provider = get_llm_provider()
        assert provider.name == "local_fallback"

    def test_get_llm_provider_singleton(self):
        """get_llm_provider should return singleton."""
        reset_llm_provider()
        p1 = get_llm_provider()
        p2 = get_llm_provider()
        assert p1 is p2

    def test_get_llm_provider_force_reload(self):
        """get_llm_provider with force_reload should create new instance."""
        reset_llm_provider()
        p1 = get_llm_provider()
        p2 = get_llm_provider(force_reload=True)
        # After force reload, should be a new instance
        # (but both should be local_fallback in test environment)
        assert p1.name == p2.name


class TestMemoryRefiner:
    """Tests for Memory Refiner service."""

    def test_memory_refiner_creation(self):
        """MemoryRefiner should be creatable."""
        refiner = MemoryRefiner()
        assert refiner.keep_recent == 3
        assert refiner.max_input_chars == 10000

    def test_memory_refiner_custom_params(self):
        """MemoryRefiner should accept custom parameters."""
        refiner = MemoryRefiner(keep_recent=5, max_input_chars=5000)
        assert refiner.keep_recent == 5
        assert refiner.max_input_chars == 5000

    @pytest.mark.asyncio
    async def test_refine_empty_memories(self):
        """Refining empty memories should return empty result."""
        refiner = MemoryRefiner()
        result = await refiner.refine(query="test", memories=[])

        assert result.success is True
        assert result.original_count == 0
        assert result.refined_content == ""
        assert result.metadata.get("reason") == "empty_input"

    @pytest.mark.asyncio
    async def test_refine_single_memory(self):
        """Refining single memory should work."""
        refiner = MemoryRefiner()
        memories = [
            {"content": "Bug fix: empty query returns None", "layer": "fact", "score": 0.9}
        ]

        result = await refiner.refine(query="bug fixes", memories=memories)

        assert result.success is True
        assert result.original_count == 1
        assert result.refined_content != ""

    @pytest.mark.asyncio
    async def test_observation_masking_preserves_recent(self):
        """Observation Masking should preserve recent N memories fully."""
        refiner = MemoryRefiner(keep_recent=2)

        memories = [
            {"content": "Memory 1 - most recent", "layer": "fact"},
            {"content": "Memory 2 - second recent", "layer": "fact"},
            {"content": "Memory 3 - this should be compressed" + "X" * 200, "layer": "fact"},
            {"content": "Memory 4 - also compressed" + "Y" * 200, "layer": "fact"},
        ]

        masked = refiner._apply_observation_masking(memories)

        # First 2 should be unchanged
        assert masked[0]["content"] == memories[0]["content"]
        assert masked[1]["content"] == memories[1]["content"]
        assert "_masked" not in masked[0]
        assert "_masked" not in masked[1]

        # Last 2 should be compressed
        assert masked[2].get("_masked") is True
        assert masked[3].get("_masked") is True
        assert len(masked[2]["content"]) < len(memories[2]["content"])
        assert len(masked[3]["content"]) < len(memories[3]["content"])

    @pytest.mark.asyncio
    async def test_observation_masking_all_recent(self):
        """If memories <= keep_recent, all should be preserved."""
        refiner = MemoryRefiner(keep_recent=5)

        memories = [
            {"content": "Memory 1", "layer": "fact"},
            {"content": "Memory 2", "layer": "fact"},
        ]

        masked = refiner._apply_observation_masking(memories)

        # All should be preserved as-is
        assert len(masked) == 2
        assert masked[0]["content"] == memories[0]["content"]
        assert masked[1]["content"] == memories[1]["content"]
        assert "_masked" not in masked[0]
        assert "_masked" not in masked[1]

    def test_compress_single_memory_short(self):
        """Short memory content should not be compressed."""
        refiner = MemoryRefiner()
        content = "Short content"
        result = refiner._compress_single_memory(content)
        assert result == content

    def test_compress_single_memory_long(self):
        """Long memory content should be truncated with ellipsis."""
        refiner = MemoryRefiner()
        content = "A" * 200
        result = refiner._compress_single_memory(content, max_len=50)
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")

    def test_format_memories(self):
        """Memory formatting should produce readable output."""
        refiner = MemoryRefiner()
        memories = [
            {"content": "First memory", "layer": "fact", "score": 0.9},
            {"content": "Second memory", "layer": "session", "score": 0.7, "_masked": True},
        ]

        formatted = refiner._format_memories(memories)

        assert "Memory 1" in formatted
        assert "Memory 2" in formatted
        assert "[fact]" in formatted
        assert "[session]" in formatted
        assert "First memory" in formatted
        assert "Second memory" in formatted
        assert "[COMPRESSED]" in formatted

    def test_estimate_tokens(self):
        """Token estimation should give reasonable estimates."""
        refiner = MemoryRefiner()

        # Short text
        assert refiner._estimate_tokens("hello") >= 1

        # Longer text (roughly 2.5 chars per token)
        text_100_chars = "A" * 100
        estimated = refiner._estimate_tokens(text_100_chars)
        assert 30 < estimated < 70  # Reasonable range

    def test_get_memory_refiner_singleton(self):
        """get_memory_refiner should return singleton."""
        reset_memory_refiner()
        r1 = get_memory_refiner()
        r2 = get_memory_refiner()
        assert r1 is r2

    def test_get_memory_refiner_force_reload(self):
        """get_memory_refiner with force_reload should create new instance."""
        reset_memory_refiner()
        r1 = get_memory_refiner()
        r2 = get_memory_refiner(force_reload=True)
        # Should be different instances
        assert r1 is not r2


class TestRefineResult:
    """Tests for RefineResult dataclass."""

    def test_refine_result_creation(self):
        """RefineResult should be creatable with all fields."""
        result = RefineResult(
            refined_content="Summary here",
            original_count=5,
            original_tokens=1000,
            refined_tokens=200,
            compression_ratio=0.2,
            llm_model="local_fallback",
            success=True,
        )

        assert result.refined_content == "Summary here"
        assert result.original_count == 5
        assert result.compression_ratio == 0.2
        assert result.success is True
        assert result.error is None

    def test_refine_result_with_error(self):
        """RefineResult should handle error case."""
        result = RefineResult(
            refined_content="",
            original_count=5,
            original_tokens=1000,
            refined_tokens=0,
            compression_ratio=0.0,
            llm_model="anthropic",
            success=False,
            error="API rate limited",
        )

        assert result.success is False
        assert result.error == "API rate limited"


class TestConfigIntegration:
    """Tests for LLM configuration integration."""

    def test_config_llm_fields_exist(self):
        """Config should have LLM-related fields."""
        from backend.config import get_config, reset_config

        reset_config()
        config = get_config()

        # Check LLM fields exist
        assert hasattr(config, "llm_provider")
        assert hasattr(config, "llm_enabled")
        assert hasattr(config, "refiner_keep_recent")
        assert hasattr(config, "refiner_max_tokens")

        # Check defaults
        assert config.llm_enabled is True
        assert config.refiner_keep_recent == 3
        assert config.refiner_max_tokens == 500

    def test_config_llm_enabled_env_var(self, monkeypatch):
        """LLM_ENABLED env var should control llm_enabled."""
        from backend.config import get_config, reset_config

        # Test true
        monkeypatch.setenv("LLM_ENABLED", "true")
        reset_config()
        config = get_config()
        assert config.llm_enabled is True

        # Test false
        monkeypatch.setenv("LLM_ENABLED", "false")
        reset_config()
        config = get_config()
        assert config.llm_enabled is False

        # Test 0
        monkeypatch.setenv("LLM_ENABLED", "0")
        reset_config()
        config = get_config()
        assert config.llm_enabled is False
