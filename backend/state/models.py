"""
State Models - 状态数据模型

定义结构化的状态文件模型，确保类型安全和一致性。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionStatus(str, Enum):
    """会话状态"""

    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class FileModification(BaseModel):
    """文件修改记录"""

    file_path: str = Field(..., description="文件路径")
    tool: str = Field(..., description="使用的工具 (Write/Edit/MultiEdit)")
    timestamp: datetime = Field(default_factory=datetime.now)
    is_source: bool = Field(default=False, description="是否是源代码文件")
    is_test: bool = Field(default=False, description="是否是测试文件")


class MemoryOperation(BaseModel):
    """Memory 操作记录"""

    tool: str = Field(..., description="Memory 工具名")
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = Field(default=True)


class SessionStatistics(BaseModel):
    """会话统计信息"""

    total_file_modifications: int = Field(default=0)
    source_files_modified: int = Field(default=0)
    test_files_modified: int = Field(default=0)
    memory_operations: int = Field(default=0)


class SessionState(BaseModel):
    """会话状态

    存储于 `.claude/state/session.json`
    """

    session_id: str = Field(..., description="会话 ID")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: datetime | None = Field(default=None)
    last_updated: datetime = Field(default_factory=datetime.now)

    # 项目信息
    project_id: str | None = Field(default=None)
    project_root: str | None = Field(default=None)

    # 统计信息
    statistics: SessionStatistics = Field(default_factory=SessionStatistics)

    # 修改的文件
    source_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)

    # 完整的修改历史（可选，用于调试）
    modifications: list[FileModification] = Field(default_factory=list)
    memory_ops: list[MemoryOperation] = Field(default_factory=list)

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        # datetime 自动序列化为 ISO 格式
        ser_json_timedelta="iso8601",
    )

    def mark_completed(self) -> None:
        """标记会话完成"""
        self.status = SessionStatus.COMPLETED
        self.ended_at = datetime.now()
        self.last_updated = datetime.now()

    def mark_interrupted(self) -> None:
        """标记会话中断"""
        self.status = SessionStatus.INTERRUPTED
        self.ended_at = datetime.now()
        self.last_updated = datetime.now()

    def add_file_modification(self, modification: FileModification) -> None:
        """添加文件修改记录"""
        self.modifications.append(modification)
        self.last_updated = datetime.now()

        # 更新统计
        self.statistics.total_file_modifications += 1
        if modification.is_source and not modification.is_test:
            if modification.file_path not in self.source_files:
                self.source_files.append(modification.file_path)
                self.statistics.source_files_modified = len(self.source_files)
        if modification.is_test:
            if modification.file_path not in self.test_files:
                self.test_files.append(modification.file_path)
                self.statistics.test_files_modified = len(self.test_files)

    def add_memory_operation(self, operation: MemoryOperation) -> None:
        """添加 Memory 操作记录"""
        self.memory_ops.append(operation)
        self.statistics.memory_operations += 1
        self.last_updated = datetime.now()


class RecommendationPriority(str, Enum):
    """测试建议优先级"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# 向后兼容别名
TestRecommendationPriority = RecommendationPriority


class RecommendationItem(BaseModel):
    """单条测试建议"""

    source_file: str = Field(..., description="源文件路径")
    recommended_tests: list[str] = Field(default_factory=list, description="推荐的测试文件")
    reason: str = Field(default="", description="推荐理由")
    priority: RecommendationPriority = Field(default=RecommendationPriority.MEDIUM)
    created_at: datetime = Field(default_factory=datetime.now)


# 向后兼容别名
TestRecommendationItem = RecommendationItem


class CoverageRecommendation(BaseModel):
    """测试覆盖建议

    存储于 `.claude/state/test-recommendation.json`
    """

    session_id: str = Field(..., description="关联的会话 ID")
    generated_at: datetime = Field(default_factory=datetime.now)

    # 推荐列表
    recommendations: list[RecommendationItem] = Field(default_factory=list)

    # 统计
    total_source_files: int = Field(default=0)
    files_with_tests: int = Field(default=0)
    files_without_tests: int = Field(default=0)

    # 未覆盖的文件（需要手动检查）
    uncovered_files: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        # datetime 自动序列化为 ISO 格式
        ser_json_timedelta="iso8601",
    )

    def add_recommendation(
        self,
        source_file: str,
        recommended_tests: list[str],
        reason: str = "",
        priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    ) -> None:
        """添加测试建议"""
        item = RecommendationItem(
            source_file=source_file,
            recommended_tests=recommended_tests,
            reason=reason,
            priority=priority,
        )
        self.recommendations.append(item)

        # 更新统计
        self.total_source_files += 1
        if recommended_tests:
            self.files_with_tests += 1
        else:
            self.files_without_tests += 1
            self.uncovered_files.append(source_file)

    def get_high_priority(self) -> list[RecommendationItem]:
        """获取高优先级建议"""
        return [r for r in self.recommendations if r.priority == RecommendationPriority.HIGH]


# 向后兼容别名
TestRecommendation = CoverageRecommendation


__all__ = [
    "SessionStatus",
    "FileModification",
    "MemoryOperation",
    "SessionStatistics",
    "SessionState",
    # New names (v2.0)
    "RecommendationPriority",
    "RecommendationItem",
    "CoverageRecommendation",
    # Backward compatibility aliases
    "TestRecommendationPriority",
    "TestRecommendationItem",
    "TestRecommendation",
]
