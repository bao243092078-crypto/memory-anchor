"""
Memory Refiner - 基于 CoDA 上下文解耦思想的记忆精炼服务

核心思想（来自 CoDA 论文）：
- 将原始记忆在独立上下文中处理，避免污染主 Agent 的上下文
- 使用 Observation Masking 策略压缩历史记忆
- 保留最近 N 条记忆的完整内容，压缩更早的记忆

用法：
    from backend.services.memory_refiner import get_memory_refiner

    refiner = get_memory_refiner()
    result = await refiner.refine(
        query="用户的问题",
        memories=[...],
        max_output_tokens=500
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from backend.services.llm_provider import LLMProvider, LLMResponse, get_llm_provider

logger = logging.getLogger(__name__)


# === Prompt 模板 ===

REFINE_SYSTEM_PROMPT = """You are a Memory Refiner for an AI assistant's memory system.

Your task is to analyze raw memories and produce a refined, concise summary that:
1. Preserves KEY DECISIONS and their rationale
2. Keeps CRITICAL FACTS (bugs fixed, architecture choices, important discoveries)
3. Removes redundant or outdated information
4. Maintains temporal context (what happened when)
5. Prioritizes information relevant to the user's current query

Output format:
- Use bullet points for clarity
- Group related memories together
- Mark uncertain information with [?]
- Keep total output under {max_tokens} tokens

Language: Match the language of the input memories (Chinese or English)."""

REFINE_USER_PROMPT = """## Current Query
{query}

## Raw Memories to Refine
{memories_text}

## Instructions
Analyze these memories and produce a refined summary that helps answer the current query.
Focus on:
- Decisions and their reasons
- Bug fixes and lessons learned
- Architecture and design choices
- Any information directly relevant to the query

Refined Summary:"""


# === 数据结构 ===

@dataclass
class RefineResult:
    """记忆精炼结果"""
    refined_content: str
    original_count: int
    original_tokens: int  # 估算
    refined_tokens: int   # 估算
    compression_ratio: float
    llm_model: str
    success: bool
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryItem:
    """单条记忆项"""
    content: str
    layer: str
    created_at: Optional[datetime] = None
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


# === Memory Refiner 核心类 ===

class MemoryRefiner:
    """
    记忆精炼器

    借鉴 CoDA 的 Executor 设计：
    - 在独立上下文中处理原始记忆
    - 使用 LLM 提取关键信息
    - 压缩输出以节省主 Agent 的上下文
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        keep_recent: int = 3,
        max_input_chars: int = 10000,
    ):
        """
        初始化 Memory Refiner

        Args:
            llm_provider: LLM Provider 实例（默认自动检测）
            keep_recent: 保留最近 N 条记忆的完整内容（Observation Masking）
            max_input_chars: 输入的最大字符数（防止超长输入）
        """
        self.llm = llm_provider or get_llm_provider()
        self.keep_recent = keep_recent
        self.max_input_chars = max_input_chars

    async def refine(
        self,
        query: str,
        memories: list[dict[str, Any]],
        max_output_tokens: int = 500,
        focus: str = "key_decisions",
    ) -> RefineResult:
        """
        精炼记忆列表

        Args:
            query: 当前用户查询（用于确定哪些记忆更相关）
            memories: 原始记忆列表（来自 search_memory）
            max_output_tokens: 输出的最大 token 数
            focus: 精炼焦点（key_decisions / bugs / all）

        Returns:
            RefineResult 包含精炼后的内容和元数据
        """
        if not memories:
            return RefineResult(
                refined_content="",
                original_count=0,
                original_tokens=0,
                refined_tokens=0,
                compression_ratio=1.0,
                llm_model=self.llm.name,
                success=True,
                metadata={"reason": "empty_input"},
            )

        # Step 1: 应用 Observation Masking
        masked_memories = self._apply_observation_masking(memories)

        # Step 2: 格式化为文本
        memories_text = self._format_memories(masked_memories)

        # Step 3: 截断过长输入
        if len(memories_text) > self.max_input_chars:
            memories_text = memories_text[:self.max_input_chars] + "\n\n[... 更多记忆已截断 ...]"

        # Step 4: 估算输入 tokens
        original_tokens = self._estimate_tokens(memories_text)

        # Step 5: 构建 prompt 并调用 LLM
        system_prompt = REFINE_SYSTEM_PROMPT.format(max_tokens=max_output_tokens)
        user_prompt = REFINE_USER_PROMPT.format(
            query=query,
            memories_text=memories_text,
        )

        response: LLMResponse = await self.llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_output_tokens,
            temperature=0.3,
        )

        if not response.success:
            return RefineResult(
                refined_content="",
                original_count=len(memories),
                original_tokens=original_tokens,
                refined_tokens=0,
                compression_ratio=0.0,
                llm_model=response.model,
                success=False,
                error=response.error,
            )

        # Step 6: 计算压缩比
        refined_tokens = self._estimate_tokens(response.content)
        compression_ratio = refined_tokens / original_tokens if original_tokens > 0 else 1.0

        return RefineResult(
            refined_content=response.content,
            original_count=len(memories),
            original_tokens=original_tokens,
            refined_tokens=refined_tokens,
            compression_ratio=compression_ratio,
            llm_model=response.model,
            success=True,
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "focus": focus,
                "kept_recent": self.keep_recent,
            },
        )

    def _apply_observation_masking(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        应用 Observation Masking 策略

        保留最近 N 条记忆的完整内容，压缩更早的记忆。
        这是 CoDA 论文中的核心策略之一。

        Args:
            memories: 原始记忆列表（按时间倒序）

        Returns:
            处理后的记忆列表
        """
        if len(memories) <= self.keep_recent:
            return memories

        result = []

        for i, memory in enumerate(memories):
            if i < self.keep_recent:
                # 保留最近的完整内容
                result.append(memory)
            else:
                # 压缩较早的记忆
                compressed = {
                    **memory,
                    "content": self._compress_single_memory(memory.get("content", "")),
                    "_masked": True,
                }
                result.append(compressed)

        return result

    def _compress_single_memory(self, content: str, max_len: int = 100) -> str:
        """
        压缩单条记忆内容

        简单策略：保留前 N 个字符 + 省略标记
        """
        if len(content) <= max_len:
            return content

        return content[:max_len] + "..."

    def _format_memories(self, memories: list[dict[str, Any]]) -> str:
        """
        格式化记忆列表为文本

        Args:
            memories: 记忆列表

        Returns:
            格式化的文本
        """
        lines = []

        for i, memory in enumerate(memories, 1):
            layer = memory.get("layer", "unknown")
            content = memory.get("content", "")
            score = memory.get("score", 0.0)
            created_at = memory.get("created_at", "")
            masked = memory.get("_masked", False)

            # 格式化时间
            time_str = ""
            if created_at:
                if isinstance(created_at, datetime):
                    time_str = created_at.strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = str(created_at)[:16]

            # 构建条目
            header = f"### Memory {i} [{layer}]"
            if score > 0:
                header += f" (relevance: {score:.2f})"
            if time_str:
                header += f" @ {time_str}"
            if masked:
                header += " [COMPRESSED]"

            lines.append(header)
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """
        粗略估算 token 数

        规则：中文约 1.5 字/token，英文约 4 字符/token
        取平均值 2.5 字符/token
        """
        return len(text) // 2 + 1


# === 单例管理 ===

_refiner: Optional[MemoryRefiner] = None


def get_memory_refiner(
    llm_provider: Optional[LLMProvider] = None,
    force_reload: bool = False,
) -> MemoryRefiner:
    """
    获取 Memory Refiner 单例

    Args:
        llm_provider: 自定义 LLM Provider
        force_reload: 强制重新创建

    Returns:
        MemoryRefiner 实例
    """
    global _refiner

    if _refiner is None or force_reload:
        _refiner = MemoryRefiner(llm_provider=llm_provider)

    return _refiner


def reset_memory_refiner():
    """重置 Memory Refiner 单例（用于测试）"""
    global _refiner
    _refiner = None


__all__ = [
    "MemoryRefiner",
    "RefineResult",
    "MemoryItem",
    "get_memory_refiner",
    "reset_memory_refiner",
]
