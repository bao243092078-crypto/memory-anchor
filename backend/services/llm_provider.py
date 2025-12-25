"""
LLM Provider - Memory Anchor LLM 抽象层

借鉴 CoDA 的 Executor 设计思想，提供独立的 LLM 调用上下文。
支持多种 LLM 后端，优雅降级到本地处理。

用法：
    from backend.services.llm_provider import get_llm_provider

    provider = get_llm_provider()
    result = await provider.refine(prompt, max_tokens=500)
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 响应结果"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    success: bool
    error: Optional[str] = None


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """检查 Provider 是否可用"""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """执行 LLM 调用"""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Provider"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> LLMResponse:
        try:
            import asyncio
            client = self._get_client()

            # Anthropic SDK 是同步的，用 to_thread 包装
            def _call():
                return client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt or "You are a helpful assistant that summarizes and refines information.",
                    messages=[{"role": "user", "content": prompt}],
                )

            response = await asyncio.to_thread(_call)

            return LLMResponse(
                content=response.content[0].text,
                model=self.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                success=True,
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return LLMResponse(
                content="",
                model=self.model,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=str(e),
            )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT Provider"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> LLMResponse:
        try:
            import asyncio
            client = self._get_client()

            def _call():
                return client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt or "You are a helpful assistant that summarizes and refines information."},
                        {"role": "user", "content": prompt},
                    ],
                )

            response = await asyncio.to_thread(_call)

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=self.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                success=True,
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return LLMResponse(
                content="",
                model=self.model,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=str(e),
            )


class LocalFallbackProvider(LLMProvider):
    """本地回退 Provider（无 LLM 时使用简单规则）"""

    @property
    def name(self) -> str:
        return "local_fallback"

    @property
    def is_available(self) -> bool:
        return True  # 始终可用

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> LLMResponse:
        # 简单的规则：截取前 N 个字符，保留结构
        content = self._simple_compress(prompt, max_tokens * 4)  # 粗略估算

        return LLMResponse(
            content=content,
            model="local_fallback",
            input_tokens=len(prompt),
            output_tokens=len(content),
            success=True,
        )

    def _simple_compress(self, text: str, max_chars: int) -> str:
        """简单的文本压缩：保留开头和结尾"""
        if len(text) <= max_chars:
            return text

        half = max_chars // 2
        return f"{text[:half]}\n\n[... 中间内容已省略 ...]\n\n{text[-half:]}"


# === 单例管理 ===

_provider: Optional[LLMProvider] = None


def get_llm_provider(
    provider_name: Optional[str] = None,
    force_reload: bool = False,
) -> LLMProvider:
    """
    获取 LLM Provider 单例

    优先级（如果未指定 provider_name）：
    1. 环境变量 LLM_PROVIDER
    2. 自动检测可用的 Provider（Anthropic > OpenAI > Local）

    Args:
        provider_name: 指定 provider（anthropic / openai / local）
        force_reload: 强制重新加载

    Returns:
        LLMProvider 实例
    """
    global _provider

    if _provider is not None and not force_reload:
        return _provider

    # 确定使用哪个 provider
    name = provider_name or os.getenv("LLM_PROVIDER", "").lower()

    if name == "anthropic":
        _provider = AnthropicProvider()
    elif name == "openai":
        _provider = OpenAIProvider()
    elif name == "local":
        _provider = LocalFallbackProvider()
    else:
        # 自动检测
        anthropic = AnthropicProvider()
        if anthropic.is_available:
            logger.info("Auto-detected Anthropic provider")
            _provider = anthropic
        else:
            openai = OpenAIProvider()
            if openai.is_available:
                logger.info("Auto-detected OpenAI provider")
                _provider = openai
            else:
                logger.warning("No LLM API key found, using local fallback")
                _provider = LocalFallbackProvider()

    return _provider


def reset_llm_provider():
    """重置 LLM Provider 单例（用于测试）"""
    global _provider
    _provider = None


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "AnthropicProvider",
    "OpenAIProvider",
    "LocalFallbackProvider",
    "get_llm_provider",
    "reset_llm_provider",
]
