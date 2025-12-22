"""
Drift Measurement Service - 偏离度计算

计算当前工作与北极星目标的语义偏离度。

算法：
1. 使用 embedding 生成北极星和工作摘要的向量
2. 计算余弦相似度
3. 转换为偏离度百分比（0% = 完全对齐, 100% = 完全偏离）

偏离度分级：
- 0-20%: 🟢 高度对齐
- 21-40%: 🟡 轻微偏离
- 41-60%: 🟠 中度偏离
- 61-80%: 🔴 严重偏离
- 81-100%: ⚫ 完全偏离
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.services.embedding import embed_text


@dataclass
class DriftResult:
    """偏离度计算结果"""
    similarity: float  # 余弦相似度 (0-1)
    drift_percent: float  # 偏离度百分比 (0-100)
    level: str  # 偏离等级
    emoji: str  # 等级图标
    message: str  # 简短说明
    north_star_summary: str  # 北极星摘要
    work_summary: str  # 工作摘要


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    计算两个向量的余弦相似度

    Returns:
        相似度值 (0-1, 1 = 完全相同)
    """
    if len(vec1) != len(vec2):
        raise ValueError(f"向量维度不匹配: {len(vec1)} vs {len(vec2)}")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def get_drift_level(drift_percent: float) -> tuple[str, str, str]:
    """
    根据偏离度返回等级、图标和说明

    Returns:
        (level, emoji, message)
    """
    if drift_percent <= 20:
        return "aligned", "🟢", "高度对齐，继续保持"
    elif drift_percent <= 40:
        return "slight", "🟡", "轻微偏离，注意方向"
    elif drift_percent <= 60:
        return "moderate", "🟠", "中度偏离，建议回顾北极星"
    elif drift_percent <= 80:
        return "severe", "🔴", "严重偏离，需要立即调整"
    else:
        return "critical", "⚫", "完全偏离，请停下来重新对齐"


def calculate_drift(
    north_star_content: str,
    work_summary: str,
) -> DriftResult:
    """
    计算工作摘要与北极星的偏离度

    Args:
        north_star_content: 北极星内容
        work_summary: 当前工作摘要

    Returns:
        DriftResult 包含偏离度和等级信息
    """
    # 生成 embedding
    north_star_vec = embed_text(north_star_content)
    work_vec = embed_text(work_summary)

    # 计算余弦相似度
    similarity = cosine_similarity(north_star_vec, work_vec)

    # 转换为偏离度（相似度越高，偏离度越低）
    # 使用 (1 - similarity) * 100 会导致偏离度过高
    # 调整公式：similarity 0.5 以下才算偏离
    # 使用分段线性映射：
    # similarity >= 0.7 -> drift 0-20%
    # similarity 0.5-0.7 -> drift 20-50%
    # similarity 0.3-0.5 -> drift 50-80%
    # similarity < 0.3 -> drift 80-100%

    if similarity >= 0.7:
        drift_percent = (0.7 - similarity) / 0.3 * 20 + 0  # 0-20%
    elif similarity >= 0.5:
        drift_percent = (0.7 - similarity) / 0.2 * 30 + 20  # 20-50%
    elif similarity >= 0.3:
        drift_percent = (0.5 - similarity) / 0.2 * 30 + 50  # 50-80%
    else:
        drift_percent = (0.3 - similarity) / 0.3 * 20 + 80  # 80-100%

    drift_percent = max(0, min(100, drift_percent))

    level, emoji, message = get_drift_level(drift_percent)

    # 提取北极星摘要（第一个非空行或标题）
    ns_lines = [l.strip() for l in north_star_content.split('\n') if l.strip()]
    ns_summary = ns_lines[0] if ns_lines else "（无内容）"
    if ns_summary.startswith('#'):
        ns_summary = ns_summary.lstrip('#').strip()

    # 工作摘要截断
    work_short = work_summary[:100] + "..." if len(work_summary) > 100 else work_summary

    return DriftResult(
        similarity=similarity,
        drift_percent=round(drift_percent, 1),
        level=level,
        emoji=emoji,
        message=message,
        north_star_summary=ns_summary,
        work_summary=work_short,
    )


def find_north_star_content(start_path: Optional[Path] = None) -> Optional[str]:
    """
    从指定路径向上查找 NORTH_STAR.md 并返回内容

    Returns:
        北极星内容或 None
    """
    cwd = start_path or Path.cwd()

    for path in [cwd, *cwd.parents]:
        north_star = path / ".ai" / "NORTH_STAR.md"
        if north_star.exists():
            return north_star.read_text(encoding="utf-8")

        north_star_root = path / "NORTH_STAR.md"
        if north_star_root.exists():
            return north_star_root.read_text(encoding="utf-8")

        if path == Path.home():
            break

    return None


__all__ = [
    "DriftResult",
    "calculate_drift",
    "cosine_similarity",
    "find_north_star_content",
    "get_drift_level",
]
