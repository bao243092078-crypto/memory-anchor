"""
Review Runner - 多视角审查并行执行器

支持：
- 四视角并行执行
- 结果聚合
- 进度回调
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from backend.services.review.base import (
    BaseReviewer,
    ReviewContext,
    ReviewFinding,
    ReviewResult,
    Severity,
)
from backend.services.review.memory_reviewer import MemoryIntegrityReviewer
from backend.services.review.performance_reviewer import PerformanceReviewer
from backend.services.review.quality_reviewer import QualityReviewer
from backend.services.review.security_reviewer import SecurityReviewer


@dataclass
class AggregatedResult:
    """聚合审查结果"""

    # 各视角结果
    results: dict[str, ReviewResult] = field(default_factory=dict)

    # 所有发现（按严重程度排序）
    all_findings: list[ReviewFinding] = field(default_factory=list)

    # 总执行时间
    total_duration: float = 0.0

    # 统计信息
    total_files: int = 0
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    # 是否全部成功
    all_success: bool = True

    # 错误信息
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def has_blocking_issues(self) -> bool:
        """是否有阻断性问题"""
        return self.critical_count > 0

    @property
    def summary(self) -> str:
        """生成摘要"""
        if self.has_blocking_issues:
            return f"🔴 发现 {self.critical_count} 个严重问题需要立即修复"
        elif self.high_count > 0:
            return f"🟠 发现 {self.high_count} 个高优先级问题建议修复"
        elif self.medium_count > 0:
            return f"🟡 发现 {self.medium_count} 个中等问题可以优化"
        elif self.total_findings > 0:
            return f"🟢 发现 {self.total_findings} 个轻微问题/建议"
        else:
            return "✅ 代码审查通过，未发现问题"


# 进度回调类型
ProgressCallback = Callable[[str, str, float], None]


class ReviewRunner:
    """审查运行器

    并行执行多视角审查，聚合结果。
    """

    def __init__(
        self,
        perspectives: list[str] | None = None,
        max_workers: int = 4,
    ):
        """初始化运行器

        Args:
            perspectives: 要运行的视角列表，默认全部
                可选: ["security", "performance", "quality", "memory"]
            max_workers: 最大并行工作线程数
        """
        self._max_workers = max_workers
        self._reviewers: dict[str, BaseReviewer] = {}

        # 注册审查器
        all_reviewers: list[BaseReviewer] = [
            SecurityReviewer(),
            PerformanceReviewer(),
            QualityReviewer(),
            MemoryIntegrityReviewer(),
        ]

        for reviewer in all_reviewers:
            if perspectives is None or reviewer.perspective in perspectives:
                self._reviewers[reviewer.perspective] = reviewer

    @property
    def perspectives(self) -> list[str]:
        """返回启用的视角列表"""
        return list(self._reviewers.keys())

    def run(
        self,
        context: ReviewContext,
        progress_callback: ProgressCallback | None = None,
    ) -> AggregatedResult:
        """运行审查

        Args:
            context: 审查上下文
            progress_callback: 进度回调函数 (perspective, status, progress)

        Returns:
            聚合审查结果
        """
        start_time = time.time()
        result = AggregatedResult()

        # 并行执行各视角审查
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {}
            for perspective, reviewer in self._reviewers.items():
                if progress_callback:
                    progress_callback(perspective, "started", 0.0)
                future = executor.submit(self._run_reviewer, reviewer, context)
                futures[future] = perspective

            # 收集结果
            completed = 0
            total = len(futures)

            for future in as_completed(futures):
                perspective = futures[future]
                completed += 1

                try:
                    review_result = future.result()
                    result.results[perspective] = review_result

                    if not review_result.success:
                        result.all_success = False
                        if review_result.error:
                            result.errors[perspective] = review_result.error

                    if progress_callback:
                        progress_callback(
                            perspective,
                            "completed" if review_result.success else "failed",
                            completed / total,
                        )

                except Exception as e:
                    result.all_success = False
                    result.errors[perspective] = str(e)

                    if progress_callback:
                        progress_callback(perspective, "error", completed / total)

        # 聚合结果
        self._aggregate_results(result)
        result.total_duration = time.time() - start_time

        return result

    def _run_reviewer(
        self,
        reviewer: BaseReviewer,
        context: ReviewContext,
    ) -> ReviewResult:
        """运行单个审查器"""
        return reviewer.review(context)

    def _aggregate_results(self, result: AggregatedResult) -> None:
        """聚合各视角结果"""
        all_findings: list[ReviewFinding] = []
        files_set: set[str] = set()

        for perspective_result in result.results.values():
            all_findings.extend(perspective_result.findings)
            # 收集审查的文件
            for finding in perspective_result.findings:
                if finding.file_path:
                    files_set.add(str(finding.file_path))

        # 按严重程度排序
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        all_findings.sort(key=lambda f: severity_order.get(f.severity, 99))

        result.all_findings = all_findings
        result.total_findings = len(all_findings)
        result.total_files = len(files_set)

        # 统计各严重程度
        result.critical_count = sum(
            1 for f in all_findings if f.severity == Severity.CRITICAL
        )
        result.high_count = sum(
            1 for f in all_findings if f.severity == Severity.HIGH
        )
        result.medium_count = sum(
            1 for f in all_findings if f.severity == Severity.MEDIUM
        )
        result.low_count = sum(
            1 for f in all_findings if f.severity == Severity.LOW
        )
        result.info_count = sum(
            1 for f in all_findings if f.severity == Severity.INFO
        )

    def run_single(
        self,
        perspective: str,
        context: ReviewContext,
    ) -> ReviewResult:
        """运行单个视角审查

        Args:
            perspective: 视角名称
            context: 审查上下文

        Returns:
            审查结果

        Raises:
            ValueError: 视角不存在
        """
        if perspective not in self._reviewers:
            raise ValueError(
                f"Unknown perspective: {perspective}. "
                f"Available: {list(self._reviewers.keys())}"
            )

        return self._reviewers[perspective].review(context)


__all__ = ["ReviewRunner", "AggregatedResult", "ProgressCallback"]
