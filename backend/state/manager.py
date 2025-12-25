"""
State Manager - 状态文件管理器

负责管理 `.claude/state/` 目录结构和状态文件的读写。

目录结构：
    .claude/
    └── state/
        ├── session.json              # 当前会话状态
        ├── test-recommendation.json  # 测试建议
        └── session-history/          # 历史会话存档
            └── session_<id>_<timestamp>.json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.state.models import (
    FileModification,
    MemoryOperation,
    SessionState,
    SessionStatus,
    TestRecommendation,
    TestRecommendationPriority,
)

logger = logging.getLogger(__name__)

# 默认状态目录
DEFAULT_STATE_DIR_NAME = ".claude/state"
SESSION_FILE = "session.json"
TEST_RECOMMENDATION_FILE = "test-recommendation.json"
SESSION_HISTORY_DIR = "session-history"

# 全局单例
_state_manager: StateManager | None = None


def find_project_root(start_path: Path | None = None) -> Path:
    """查找项目根目录

    按优先级查找：
    1. 包含 .git 目录
    2. 包含 pyproject.toml
    3. 包含 package.json
    4. 包含 CLAUDE.md
    5. 当前工作目录

    Args:
        start_path: 起始搜索路径

    Returns:
        项目根目录路径
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # 向上查找
    for _ in range(10):  # 最多向上 10 层
        # 检查标识文件
        markers = [".git", "pyproject.toml", "package.json", "CLAUDE.md"]
        for marker in markers:
            if (current / marker).exists():
                return current

        # 到达根目录
        parent = current.parent
        if parent == current:
            break
        current = parent

    # 回退到起始目录
    return start_path.resolve()


class StateManager:
    """状态文件管理器

    管理项目级别的状态文件，提供读写接口。
    """

    def __init__(self, project_root: str | Path | None = None):
        """初始化状态管理器

        Args:
            project_root: 项目根目录，不指定时自动检测
        """
        if project_root is None:
            self._project_root = find_project_root()
        else:
            self._project_root = Path(project_root).resolve()

        self._state_dir = self._project_root / DEFAULT_STATE_DIR_NAME
        self._current_session: SessionState | None = None

    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return self._project_root

    @property
    def state_dir(self) -> Path:
        """状态目录路径"""
        return self._state_dir

    @property
    def session_file(self) -> Path:
        """会话状态文件路径"""
        return self._state_dir / SESSION_FILE

    @property
    def test_recommendation_file(self) -> Path:
        """测试建议文件路径"""
        return self._state_dir / TEST_RECOMMENDATION_FILE

    @property
    def session_history_dir(self) -> Path:
        """会话历史目录路径"""
        return self._state_dir / SESSION_HISTORY_DIR

    def ensure_dirs(self) -> None:
        """确保目录结构存在"""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self.session_history_dir.mkdir(parents=True, exist_ok=True)

    # ============ Session Management ============

    def start_session(
        self,
        session_id: str | None = None,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """开始新会话

        Args:
            session_id: 会话 ID，不指定时自动生成
            project_id: 项目 ID
            metadata: 额外元数据

        Returns:
            新创建的会话状态
        """
        self.ensure_dirs()

        # 如果有旧会话，先归档
        if self.session_file.exists():
            try:
                old_session = self.load_session()
                if old_session and old_session.status == SessionStatus.ACTIVE:
                    old_session.mark_interrupted()
                    self.archive_session(old_session)
            except Exception as e:
                logger.warning(f"Failed to archive old session: {e}")

        # 生成会话 ID
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建新会话
        session = SessionState(
            session_id=session_id,
            status=SessionStatus.ACTIVE,
            project_id=project_id or os.environ.get("MCP_MEMORY_PROJECT_ID"),
            project_root=str(self._project_root),
            metadata=metadata or {},
        )

        self._current_session = session
        self.save_session(session)

        logger.info(f"Started new session: {session_id}")
        return session

    def load_session(self) -> SessionState | None:
        """加载当前会话状态

        Returns:
            会话状态，文件不存在时返回 None
        """
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = SessionState(**data)
            self._current_session = session
            return session
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def save_session(self, session: SessionState | None = None) -> Path:
        """保存会话状态

        Args:
            session: 要保存的会话，不指定时使用当前会话

        Returns:
            保存的文件路径
        """
        self.ensure_dirs()

        if session is None:
            session = self._current_session
        if session is None:
            raise ValueError("No session to save")

        session.last_updated = datetime.now()

        with open(self.session_file, "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2))

        self._current_session = session
        return self.session_file

    def end_session(self, session: SessionState | None = None) -> Path:
        """结束会话并归档

        Args:
            session: 要结束的会话，不指定时使用当前会话

        Returns:
            归档文件路径
        """
        if session is None:
            session = self._current_session or self.load_session()
        if session is None:
            raise ValueError("No session to end")

        session.mark_completed()
        self.save_session(session)

        # 归档
        archive_path = self.archive_session(session)

        # 删除当前会话文件（已归档）
        if self.session_file.exists():
            self.session_file.unlink()

        self._current_session = None

        return archive_path

    def archive_session(self, session: SessionState) -> Path:
        """归档会话到历史目录

        Args:
            session: 要归档的会话

        Returns:
            归档文件路径
        """
        self.ensure_dirs()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{session.session_id}_{timestamp}.json"
        archive_path = self.session_history_dir / filename

        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2))

        logger.info(f"Session archived: {archive_path}")
        return archive_path

    def get_current_session(self) -> SessionState | None:
        """获取当前会话

        Returns:
            当前会话状态
        """
        if self._current_session is None:
            self._current_session = self.load_session()
        return self._current_session

    # ============ File Modification Tracking ============

    def record_file_modification(
        self,
        file_path: str,
        tool: str,
        is_source: bool = False,
        is_test: bool = False,
    ) -> None:
        """记录文件修改

        Args:
            file_path: 文件路径
            tool: 使用的工具
            is_source: 是否是源代码文件
            is_test: 是否是测试文件
        """
        session = self.get_current_session()
        if session is None:
            logger.warning("No active session for file modification")
            return

        modification = FileModification(
            file_path=file_path,
            tool=tool,
            is_source=is_source,
            is_test=is_test,
        )
        session.add_file_modification(modification)
        self.save_session(session)

    def record_memory_operation(
        self,
        tool: str,
        success: bool = True,
    ) -> None:
        """记录 Memory 操作

        Args:
            tool: Memory 工具名
            success: 操作是否成功
        """
        session = self.get_current_session()
        if session is None:
            logger.warning("No active session for memory operation")
            return

        operation = MemoryOperation(tool=tool, success=success)
        session.add_memory_operation(operation)
        self.save_session(session)

    # ============ Test Recommendations ============

    def save_test_recommendations(
        self,
        recommendations: TestRecommendation,
    ) -> Path:
        """保存测试建议

        Args:
            recommendations: 测试建议

        Returns:
            保存的文件路径
        """
        self.ensure_dirs()

        with open(self.test_recommendation_file, "w", encoding="utf-8") as f:
            f.write(recommendations.model_dump_json(indent=2))

        logger.info(f"Test recommendations saved: {self.test_recommendation_file}")
        return self.test_recommendation_file

    def load_test_recommendations(self) -> TestRecommendation | None:
        """加载测试建议

        Returns:
            测试建议，文件不存在时返回 None
        """
        if not self.test_recommendation_file.exists():
            return None

        try:
            with open(self.test_recommendation_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TestRecommendation(**data)
        except Exception as e:
            logger.error(f"Failed to load test recommendations: {e}")
            return None

    def generate_test_recommendations(
        self,
        session: SessionState | None = None,
        test_mapping: dict[str, list[str]] | None = None,
    ) -> TestRecommendation:
        """根据会话生成测试建议

        Args:
            session: 会话状态，不指定时使用当前会话
            test_mapping: 源文件到测试文件的映射规则

        Returns:
            生成的测试建议
        """
        if session is None:
            session = self.get_current_session()
        if session is None:
            raise ValueError("No session for generating recommendations")

        recommendations = TestRecommendation(session_id=session.session_id)

        # 获取修改的源文件
        source_files = session.source_files
        test_files_modified = set(session.test_files)

        for source_file in source_files:
            # 尝试推断测试文件
            recommended_tests = self._infer_test_files(source_file, test_mapping)

            # 检查是否已有测试修改
            has_test_coverage = any(t in test_files_modified for t in recommended_tests)

            # 确定优先级
            if not recommended_tests:
                priority = TestRecommendationPriority.HIGH
                reason = "No test file mapping found"
            elif has_test_coverage:
                priority = TestRecommendationPriority.LOW
                reason = "Test file already modified"
            else:
                priority = TestRecommendationPriority.MEDIUM
                reason = "Test file not modified in this session"

            recommendations.add_recommendation(
                source_file=source_file,
                recommended_tests=recommended_tests,
                reason=reason,
                priority=priority,
            )

        # 保存
        self.save_test_recommendations(recommendations)
        return recommendations

    def _infer_test_files(
        self,
        source_file: str,
        test_mapping: dict[str, list[str]] | None = None,
    ) -> list[str]:
        """推断源文件对应的测试文件

        Args:
            source_file: 源文件路径
            test_mapping: 自定义映射规则

        Returns:
            推荐的测试文件列表
        """
        # 优先使用自定义映射
        if test_mapping and source_file in test_mapping:
            return test_mapping[source_file]

        # 默认推断规则
        path = Path(source_file)
        name = path.stem
        suffix = path.suffix

        inferred = []

        # Python: src/foo.py -> tests/test_foo.py
        if suffix == ".py":
            # 尝试 tests/test_<name>.py
            test_path = path.parent.parent / "tests" / f"test_{name}.py"
            inferred.append(str(test_path))

            # 尝试 test_<name>.py 在同目录
            test_path_same = path.parent / f"test_{name}.py"
            inferred.append(str(test_path_same))

        # TypeScript/JavaScript: src/foo.ts -> src/foo.test.ts or __tests__/foo.test.ts
        elif suffix in (".ts", ".tsx", ".js", ".jsx"):
            # 同目录 .test.ts
            test_path = path.parent / f"{name}.test{suffix}"
            inferred.append(str(test_path))

            # __tests__ 目录
            test_path_dir = path.parent / "__tests__" / f"{name}.test{suffix}"
            inferred.append(str(test_path_dir))

        return inferred

    # ============ Cleanup ============

    def clear_state(self) -> None:
        """清除所有状态（危险操作，仅用于测试）"""
        import shutil

        if self._state_dir.exists():
            shutil.rmtree(self._state_dir)
        self._current_session = None
        logger.warning(f"State directory cleared: {self._state_dir}")


def get_state_manager(project_root: str | Path | None = None) -> StateManager:
    """获取全局 StateManager 单例

    Args:
        project_root: 项目根目录

    Returns:
        StateManager 实例
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(project_root)
    return _state_manager


def reset_state_manager() -> None:
    """重置全局 StateManager 单例（用于测试）"""
    global _state_manager
    _state_manager = None


__all__ = [
    "StateManager",
    "get_state_manager",
    "reset_state_manager",
    "find_project_root",
]
