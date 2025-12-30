"""
conflict_detector.py - 记忆冲突检测模块 (v3.0)

基于规则的冲突检测引擎（不使用 LLM，因 MemoryAgentBench 显示多跳冲突仅 6-7% 准确率）。

冲突类型：
1. temporal: 同一实体的新旧记录（valid_at 时间重叠）
2. source: 不同来源的矛盾信息（created_by 不同但内容相似）
3. confidence: 低置信度 vs 高置信度冲突

检测策略：
- 使用向量相似度找到"同一实体"的候选记忆
- 应用规则判断是否存在冲突
- 返回冲突结果和解决建议

参考论文：
- MemoryAgentBench (arXiv:2507.05257) - 冲突检测基准
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class ConflictType(str, Enum):
    """冲突类型"""
    TEMPORAL = "temporal"      # 时间冲突：同一实体的新旧记录
    SOURCE = "source"          # 来源冲突：不同来源的矛盾信息
    CONFIDENCE = "confidence"  # 置信度冲突：低置信度 vs 高置信度
    SEMANTIC = "semantic"      # 语义冲突：内容矛盾但高相似度


class ConflictSeverity(str, Enum):
    """冲突严重程度"""
    LOW = "low"        # 低：仅提示，可忽略
    MEDIUM = "medium"  # 中：建议检查
    HIGH = "high"      # 高：强烈建议处理


@dataclass
class ConflictResult:
    """
    冲突检测结果

    Attributes:
        has_conflict: 是否存在冲突
        conflict_type: 冲突类型
        severity: 冲突严重程度
        conflicting_memories: 冲突的记忆 ID 列表
        resolution_hint: 解决建议
        details: 详细信息
    """
    has_conflict: bool
    conflict_type: Optional[ConflictType] = None
    severity: ConflictSeverity = ConflictSeverity.LOW
    conflicting_memories: List[UUID] = field(default_factory=list)
    resolution_hint: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "has_conflict": self.has_conflict,
            "conflict_type": self.conflict_type.value if self.conflict_type else None,
            "severity": self.severity.value,
            "conflicting_memories": [str(m) for m in self.conflicting_memories],
            "resolution_hint": self.resolution_hint,
            "details": self.details,
        }


@dataclass
class ConflictDetectorConfig:
    """
    冲突检测器配置

    Attributes:
        similarity_threshold: 相似度阈值（高于此值认为是"同一实体"）
        temporal_overlap_days: 时间重叠检测天数
        confidence_diff_threshold: 置信度差异阈值
        enabled: 是否启用冲突检测
    """
    similarity_threshold: float = 0.85  # 相似度 >= 0.85 认为是同一实体
    temporal_overlap_days: int = 7      # 7 天内的记忆可能存在时间冲突
    confidence_diff_threshold: float = 0.3  # 置信度差异 > 0.3 触发冲突
    enabled: bool = True


class ConflictDetector:
    """
    记忆冲突检测器

    使用规则引擎检测潜在的记忆冲突。

    Example:
        >>> detector = ConflictDetector(search_service)
        >>> result = detector.detect(
        ...     content="患者今天吃了苹果",
        ...     layer="verified_fact",
        ...     project_id="阿默斯海默症"
        ... )
        >>> if result.has_conflict:
        ...     print(f"检测到 {result.conflict_type} 冲突: {result.resolution_hint}")
    """

    def __init__(
        self,
        search_service: Any,  # SearchService，避免循环导入
        config: Optional[ConflictDetectorConfig] = None,
    ):
        """
        初始化冲突检测器

        Args:
            search_service: 搜索服务实例（用于向量相似度检索）
            config: 检测器配置
        """
        self.search_service = search_service
        self.config = config or ConflictDetectorConfig()

    def detect(
        self,
        content: str,
        layer: str,
        project_id: str,
        confidence: float = 1.0,
        created_by: str = "caregiver",
        valid_at: Optional[datetime] = None,
        **kwargs,
    ) -> ConflictResult:
        """
        检测新记忆与现有记忆的冲突

        Args:
            content: 新记忆内容
            layer: 记忆层级
            project_id: 项目 ID
            confidence: 置信度
            created_by: 创建者
            valid_at: 生效时间
            **kwargs: 其他参数

        Returns:
            ConflictResult: 冲突检测结果
        """
        if not self.config.enabled:
            return ConflictResult(has_conflict=False)

        # 1. 使用向量相似度搜索相似记忆
        similar_memories = self._find_similar_memories(
            content=content,
            layer=layer,
            project_id=project_id,
        )

        if not similar_memories:
            return ConflictResult(has_conflict=False)

        # 2. 检测各类冲突
        conflicts: List[ConflictResult] = []

        # 2.1 时间冲突检测
        temporal_conflict = self._check_temporal_conflict(
            similar_memories=similar_memories,
            valid_at=valid_at or datetime.now(timezone.utc),
        )
        if temporal_conflict.has_conflict:
            conflicts.append(temporal_conflict)

        # 2.2 来源冲突检测
        source_conflict = self._check_source_conflict(
            similar_memories=similar_memories,
            created_by=created_by,
        )
        if source_conflict.has_conflict:
            conflicts.append(source_conflict)

        # 2.3 置信度冲突检测
        confidence_conflict = self._check_confidence_conflict(
            similar_memories=similar_memories,
            new_confidence=confidence,
        )
        if confidence_conflict.has_conflict:
            conflicts.append(confidence_conflict)

        # 3. 返回最严重的冲突
        if conflicts:
            # 按严重程度排序
            severity_order = {
                ConflictSeverity.HIGH: 0,
                ConflictSeverity.MEDIUM: 1,
                ConflictSeverity.LOW: 2,
            }
            conflicts.sort(key=lambda c: severity_order.get(c.severity, 99))
            return conflicts[0]

        return ConflictResult(has_conflict=False)

    def detect_all(
        self,
        content: str,
        layer: str,
        project_id: str,
        confidence: float = 1.0,
        created_by: str = "caregiver",
        valid_at: Optional[datetime] = None,
        **kwargs,
    ) -> List[ConflictResult]:
        """
        检测所有冲突（不只返回最严重的）

        Args:
            与 detect() 相同

        Returns:
            List[ConflictResult]: 所有检测到的冲突
        """
        if not self.config.enabled:
            return []

        similar_memories = self._find_similar_memories(
            content=content,
            layer=layer,
            project_id=project_id,
        )

        if not similar_memories:
            return []

        conflicts: List[ConflictResult] = []

        temporal_conflict = self._check_temporal_conflict(
            similar_memories=similar_memories,
            valid_at=valid_at or datetime.now(timezone.utc),
        )
        if temporal_conflict.has_conflict:
            conflicts.append(temporal_conflict)

        source_conflict = self._check_source_conflict(
            similar_memories=similar_memories,
            created_by=created_by,
        )
        if source_conflict.has_conflict:
            conflicts.append(source_conflict)

        confidence_conflict = self._check_confidence_conflict(
            similar_memories=similar_memories,
            new_confidence=confidence,
        )
        if confidence_conflict.has_conflict:
            conflicts.append(confidence_conflict)

        return conflicts

    def _find_similar_memories(
        self,
        content: str,
        layer: str,
        project_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        使用向量相似度搜索相似记忆

        Args:
            content: 搜索内容
            layer: 记忆层级
            project_id: 项目 ID
            limit: 返回数量限制

        Returns:
            相似记忆列表（包含相似度分数）
        """
        try:
            results = self.search_service.search(
                query=content,
                layer=layer,
                project_id=project_id,
                limit=limit,
                include_expired=True,  # 包含已过期记忆以检测时间冲突
            )

            # 过滤高相似度的结果
            similar = [
                r for r in results
                if r.get("score", 0) >= self.config.similarity_threshold
            ]

            return similar

        except Exception as e:
            # 搜索失败时不阻止写入，仅记录
            import logging
            logging.warning(f"ConflictDetector: 搜索相似记忆失败: {e}")
            return []

    def _check_temporal_conflict(
        self,
        similar_memories: List[Dict[str, Any]],
        valid_at: datetime,
    ) -> ConflictResult:
        """
        检测时间冲突

        规则：如果存在高相似度记忆，且 valid_at 时间接近（重叠），
        可能是对同一事件的重复记录或更新。

        Args:
            similar_memories: 相似记忆列表
            valid_at: 新记忆的生效时间

        Returns:
            ConflictResult
        """
        conflicting_ids: List[UUID] = []
        max_overlap_days = 0

        for memory in similar_memories:
            memory_valid_at = memory.get("valid_at")
            if memory_valid_at:
                if isinstance(memory_valid_at, str):
                    try:
                        memory_valid_at = datetime.fromisoformat(
                            memory_valid_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                elif isinstance(memory_valid_at, (int, float)):
                    memory_valid_at = datetime.fromtimestamp(
                        memory_valid_at, tz=timezone.utc
                    )

                # 计算时间差
                time_diff = abs((valid_at - memory_valid_at).days)
                if time_diff <= self.config.temporal_overlap_days:
                    memory_id = memory.get("id")
                    if memory_id:
                        if isinstance(memory_id, str):
                            try:
                                conflicting_ids.append(UUID(memory_id))
                            except ValueError:
                                pass
                        elif isinstance(memory_id, UUID):
                            conflicting_ids.append(memory_id)
                    max_overlap_days = max(max_overlap_days, time_diff)

        if conflicting_ids:
            return ConflictResult(
                has_conflict=True,
                conflict_type=ConflictType.TEMPORAL,
                severity=ConflictSeverity.MEDIUM if max_overlap_days <= 1 else ConflictSeverity.LOW,
                conflicting_memories=conflicting_ids,
                resolution_hint=f"检测到 {len(conflicting_ids)} 条时间相近的相似记忆，"
                                f"可能是重复记录。建议检查是否需要更新而非新增。",
                details={
                    "overlap_days": max_overlap_days,
                    "threshold_days": self.config.temporal_overlap_days,
                },
            )

        return ConflictResult(has_conflict=False)

    def _check_source_conflict(
        self,
        similar_memories: List[Dict[str, Any]],
        created_by: str,
    ) -> ConflictResult:
        """
        检测来源冲突

        规则：如果存在高相似度记忆，但创建者不同，
        可能存在来源冲突（不同来源的矛盾信息）。

        Args:
            similar_memories: 相似记忆列表
            created_by: 新记忆的创建者

        Returns:
            ConflictResult
        """
        conflicting_ids: List[UUID] = []
        conflicting_sources: set = set()

        for memory in similar_memories:
            memory_created_by = memory.get("created_by", "unknown")
            if memory_created_by != created_by:
                memory_id = memory.get("id")
                if memory_id:
                    if isinstance(memory_id, str):
                        try:
                            conflicting_ids.append(UUID(memory_id))
                        except ValueError:
                            pass
                    elif isinstance(memory_id, UUID):
                        conflicting_ids.append(memory_id)
                    conflicting_sources.add(memory_created_by)

        if conflicting_ids:
            return ConflictResult(
                has_conflict=True,
                conflict_type=ConflictType.SOURCE,
                severity=ConflictSeverity.MEDIUM,
                conflicting_memories=conflicting_ids,
                resolution_hint=f"检测到来自不同来源 ({', '.join(conflicting_sources)}) 的相似记忆。"
                                f"建议核实信息一致性。",
                details={
                    "new_source": created_by,
                    "conflicting_sources": list(conflicting_sources),
                },
            )

        return ConflictResult(has_conflict=False)

    def _check_confidence_conflict(
        self,
        similar_memories: List[Dict[str, Any]],
        new_confidence: float,
    ) -> ConflictResult:
        """
        检测置信度冲突

        规则：如果存在高相似度记忆，但置信度差异较大，
        可能存在置信度冲突。

        Args:
            similar_memories: 相似记忆列表
            new_confidence: 新记忆的置信度

        Returns:
            ConflictResult
        """
        conflicting_ids: List[UUID] = []
        max_diff = 0.0
        existing_confidence = 0.0

        for memory in similar_memories:
            memory_confidence = memory.get("confidence", 1.0)
            if isinstance(memory_confidence, (int, float)):
                diff = abs(new_confidence - memory_confidence)
                if diff >= self.config.confidence_diff_threshold:
                    memory_id = memory.get("id")
                    if memory_id:
                        if isinstance(memory_id, str):
                            try:
                                conflicting_ids.append(UUID(memory_id))
                            except ValueError:
                                pass
                        elif isinstance(memory_id, UUID):
                            conflicting_ids.append(memory_id)
                    if diff > max_diff:
                        max_diff = diff
                        existing_confidence = memory_confidence

        if conflicting_ids:
            # 新记忆置信度更高时，严重程度较低
            severity = (
                ConflictSeverity.LOW
                if new_confidence > existing_confidence
                else ConflictSeverity.MEDIUM
            )

            hint = (
                f"新记忆置信度 ({new_confidence:.2f}) 与现有记忆 ({existing_confidence:.2f}) "
                f"差异较大 (差值: {max_diff:.2f})。"
            )
            if new_confidence > existing_confidence:
                hint += " 新记忆置信度更高，可能是更可靠的信息来源。"
            else:
                hint += " 现有记忆置信度更高，建议核实新信息的可靠性。"

            return ConflictResult(
                has_conflict=True,
                conflict_type=ConflictType.CONFIDENCE,
                severity=severity,
                conflicting_memories=conflicting_ids,
                resolution_hint=hint,
                details={
                    "new_confidence": new_confidence,
                    "existing_confidence": existing_confidence,
                    "difference": max_diff,
                },
            )

        return ConflictResult(has_conflict=False)

    def scan_project(
        self,
        project_id: str,
        layer: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        扫描项目中的潜在冲突

        用于 CLI 命令 `./ma conflicts --project NAME`

        Args:
            project_id: 项目 ID
            layer: 可选的层级过滤
            limit: 扫描记忆数量限制

        Returns:
            冲突报告列表
        """
        conflicts_report: List[Dict[str, Any]] = []

        try:
            # 获取项目中的所有记忆
            all_memories = self.search_service.search(
                query="",  # 空查询获取所有
                project_id=project_id,
                layer=layer,
                limit=limit,
                include_expired=True,
            )

            # 两两比较检测冲突
            checked_pairs: set = set()

            for i, memory in enumerate(all_memories):
                memory_id = memory.get("id", "")
                content = memory.get("content", "")

                if not content:
                    continue

                # 查找与当前记忆相似的其他记忆
                similar = self._find_similar_memories(
                    content=content,
                    layer=memory.get("layer", "verified_fact"),
                    project_id=project_id,
                    limit=10,
                )

                for other in similar:
                    other_id = other.get("id", "")
                    if other_id == memory_id:
                        continue

                    # 避免重复检查同一对
                    pair_key = tuple(sorted([str(memory_id), str(other_id)]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)

                    # 检测所有冲突类型
                    conflicts = self.detect_all(
                        content=content,
                        layer=memory.get("layer", "verified_fact"),
                        project_id=project_id,
                        confidence=memory.get("confidence", 1.0),
                        created_by=memory.get("created_by", "unknown"),
                        valid_at=memory.get("valid_at"),
                    )

                    for conflict in conflicts:
                        if conflict.has_conflict:
                            conflicts_report.append({
                                "memory_id": str(memory_id),
                                "memory_content": content[:100] + "..." if len(content) > 100 else content,
                                "conflict": conflict.to_dict(),
                            })

        except Exception as e:
            import logging
            logging.error(f"ConflictDetector.scan_project 失败: {e}")

        return conflicts_report
