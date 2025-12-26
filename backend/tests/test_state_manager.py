"""
Tests for State Manager.

测试状态文件管理：
- 目录结构创建
- 会话状态管理
- 测试建议生成
"""

import json
from pathlib import Path

import pytest

from backend.state import (
    SessionState,
    StateManager,
    TestRecommendation,
    get_state_manager,
    reset_state_manager,
)
from backend.state.manager import find_project_root
from backend.state.models import (
    FileModification,
    MemoryOperation,
    SessionStatus,
    TestRecommendationPriority,
)


class TestFindProjectRoot:
    """测试项目根目录查找"""

    def test_find_git_directory(self, tmp_path: Path) -> None:
        """测试查找 .git 目录"""
        # 创建 .git 目录
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # 创建子目录
        sub_dir = tmp_path / "src" / "module"
        sub_dir.mkdir(parents=True)

        # 从子目录查找
        found = find_project_root(sub_dir)
        assert found == tmp_path

    def test_find_pyproject_toml(self, tmp_path: Path) -> None:
        """测试查找 pyproject.toml"""
        (tmp_path / "pyproject.toml").touch()
        sub_dir = tmp_path / "backend"
        sub_dir.mkdir()

        found = find_project_root(sub_dir)
        assert found == tmp_path

    def test_find_package_json(self, tmp_path: Path) -> None:
        """测试查找 package.json"""
        (tmp_path / "package.json").touch()
        sub_dir = tmp_path / "src"
        sub_dir.mkdir()

        found = find_project_root(sub_dir)
        assert found == tmp_path

    def test_fallback_to_start_path(self, tmp_path: Path) -> None:
        """测试无标识文件时回退到起始目录"""
        sub_dir = tmp_path / "some" / "path"
        sub_dir.mkdir(parents=True)

        found = find_project_root(sub_dir)
        assert found == sub_dir


class TestSessionState:
    """测试会话状态模型"""

    def test_create_session(self) -> None:
        """测试创建会话"""
        session = SessionState(session_id="test-123")

        assert session.session_id == "test-123"
        assert session.status == SessionStatus.ACTIVE
        assert session.statistics.total_file_modifications == 0

    def test_mark_completed(self) -> None:
        """测试标记完成"""
        session = SessionState(session_id="test-123")
        session.mark_completed()

        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None

    def test_mark_interrupted(self) -> None:
        """测试标记中断"""
        session = SessionState(session_id="test-123")
        session.mark_interrupted()

        assert session.status == SessionStatus.INTERRUPTED
        assert session.ended_at is not None

    def test_add_file_modification(self) -> None:
        """测试添加文件修改"""
        session = SessionState(session_id="test-123")

        modification = FileModification(
            file_path="/src/main.py",
            tool="Write",
            is_source=True,
            is_test=False,
        )
        session.add_file_modification(modification)

        assert session.statistics.total_file_modifications == 1
        assert session.statistics.source_files_modified == 1
        assert "/src/main.py" in session.source_files

    def test_add_test_file_modification(self) -> None:
        """测试添加测试文件修改"""
        session = SessionState(session_id="test-123")

        modification = FileModification(
            file_path="/tests/test_main.py",
            tool="Write",
            is_source=True,
            is_test=True,
        )
        session.add_file_modification(modification)

        assert session.statistics.test_files_modified == 1
        assert "/tests/test_main.py" in session.test_files

    def test_add_memory_operation(self) -> None:
        """测试添加 Memory 操作"""
        session = SessionState(session_id="test-123")

        operation = MemoryOperation(tool="add_memory", success=True)
        session.add_memory_operation(operation)

        assert session.statistics.memory_operations == 1
        assert len(session.memory_ops) == 1


class TestStateManager:
    """测试 StateManager"""

    @pytest.fixture(autouse=True)
    def setup_temp_project(self, tmp_path: Path):
        """设置临时项目目录"""
        # 创建项目标识
        (tmp_path / "pyproject.toml").touch()

        # 创建 StateManager
        self.manager = StateManager(project_root=tmp_path)
        self.tmp_path = tmp_path

        yield

        # 清理
        reset_state_manager()

    def test_project_root(self) -> None:
        """测试项目根目录"""
        assert self.manager.project_root == self.tmp_path

    def test_state_dir(self) -> None:
        """测试状态目录"""
        assert self.manager.state_dir == self.tmp_path / ".claude" / "state"

    def test_ensure_dirs(self) -> None:
        """测试目录创建"""
        self.manager.ensure_dirs()

        assert self.manager.state_dir.exists()
        assert self.manager.session_history_dir.exists()

    def test_start_session(self) -> None:
        """测试开始会话"""
        session = self.manager.start_session(session_id="test-sess-1")

        assert session.session_id == "test-sess-1"
        assert session.status == SessionStatus.ACTIVE
        assert self.manager.session_file.exists()

    def test_start_session_auto_id(self) -> None:
        """测试自动生成会话 ID"""
        session = self.manager.start_session()

        assert session.session_id is not None
        assert len(session.session_id) > 0

    def test_load_session(self) -> None:
        """测试加载会话"""
        # 创建会话
        original = self.manager.start_session(session_id="load-test")
        original.metadata["test"] = "value"
        self.manager.save_session(original)

        # 重新加载
        loaded = self.manager.load_session()

        assert loaded is not None
        assert loaded.session_id == "load-test"
        assert loaded.metadata["test"] == "value"

    def test_load_session_not_exists(self) -> None:
        """测试加载不存在的会话"""
        loaded = self.manager.load_session()
        assert loaded is None

    def test_save_session(self) -> None:
        """测试保存会话"""
        session = SessionState(session_id="save-test")
        path = self.manager.save_session(session)

        assert path.exists()

        # 验证内容
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["session_id"] == "save-test"

    def test_end_session(self) -> None:
        """测试结束会话"""
        _session = self.manager.start_session(session_id="end-test")  # noqa: F841
        archive_path = self.manager.end_session()

        assert archive_path.exists()
        assert "end-test" in archive_path.name
        assert self.manager.get_current_session() is None

    def test_archive_session(self) -> None:
        """测试归档会话"""
        session = SessionState(session_id="archive-test")
        archive_path = self.manager.archive_session(session)

        assert archive_path.exists()
        assert archive_path.parent == self.manager.session_history_dir

    def test_record_file_modification(self) -> None:
        """测试记录文件修改"""
        self.manager.start_session(session_id="record-test")
        self.manager.record_file_modification(
            file_path="/src/app.py",
            tool="Write",
            is_source=True,
            is_test=False,
        )

        session = self.manager.get_current_session()
        assert session is not None
        assert session.statistics.total_file_modifications == 1

    def test_record_memory_operation(self) -> None:
        """测试记录 Memory 操作"""
        self.manager.start_session(session_id="mem-test")
        self.manager.record_memory_operation(tool="add_memory")

        session = self.manager.get_current_session()
        assert session is not None
        assert session.statistics.memory_operations == 1


class TestTestRecommendations:
    """测试测试建议功能"""

    @pytest.fixture(autouse=True)
    def setup_temp_project(self, tmp_path: Path):
        """设置临时项目目录"""
        (tmp_path / "pyproject.toml").touch()
        self.manager = StateManager(project_root=tmp_path)
        self.tmp_path = tmp_path
        yield
        reset_state_manager()

    def test_create_recommendation(self) -> None:
        """测试创建测试建议"""
        rec = TestRecommendation(session_id="test-123")
        rec.add_recommendation(
            source_file="/src/main.py",
            recommended_tests=["/tests/test_main.py"],
            reason="Standard mapping",
            priority=TestRecommendationPriority.MEDIUM,
        )

        assert len(rec.recommendations) == 1
        assert rec.total_source_files == 1
        assert rec.files_with_tests == 1

    def test_save_test_recommendations(self) -> None:
        """测试保存测试建议"""
        rec = TestRecommendation(session_id="save-rec-test")
        rec.add_recommendation(
            source_file="/src/app.py",
            recommended_tests=[],
            reason="No test found",
            priority=TestRecommendationPriority.HIGH,
        )

        path = self.manager.save_test_recommendations(rec)

        assert path.exists()
        assert path == self.manager.test_recommendation_file

    def test_load_test_recommendations(self) -> None:
        """测试加载测试建议"""
        # 创建并保存
        rec = TestRecommendation(session_id="load-rec-test")
        rec.add_recommendation(
            source_file="/src/lib.py",
            recommended_tests=["/tests/test_lib.py"],
        )
        self.manager.save_test_recommendations(rec)

        # 重新加载
        loaded = self.manager.load_test_recommendations()

        assert loaded is not None
        assert loaded.session_id == "load-rec-test"
        assert len(loaded.recommendations) == 1

    def test_generate_test_recommendations(self) -> None:
        """测试生成测试建议"""
        # 创建会话并添加文件修改
        session = self.manager.start_session(session_id="gen-rec-test")

        # 添加源文件修改
        mod1 = FileModification(
            file_path="/src/service.py",
            tool="Write",
            is_source=True,
            is_test=False,
        )
        session.add_file_modification(mod1)

        # 添加测试文件修改
        mod2 = FileModification(
            file_path="/tests/test_utils.py",
            tool="Write",
            is_source=True,
            is_test=True,
        )
        session.add_file_modification(mod2)

        self.manager.save_session(session)

        # 生成建议
        rec = self.manager.generate_test_recommendations()

        assert rec.session_id == "gen-rec-test"
        assert rec.total_source_files == 1
        assert len(rec.recommendations) == 1

    def test_get_high_priority(self) -> None:
        """测试获取高优先级建议"""
        rec = TestRecommendation(session_id="prio-test")
        rec.add_recommendation(
            source_file="/src/a.py",
            recommended_tests=[],
            priority=TestRecommendationPriority.HIGH,
        )
        rec.add_recommendation(
            source_file="/src/b.py",
            recommended_tests=["/tests/test_b.py"],
            priority=TestRecommendationPriority.MEDIUM,
        )

        high_prio = rec.get_high_priority()
        assert len(high_prio) == 1
        assert high_prio[0].source_file == "/src/a.py"


class TestStateManagerSingleton:
    """测试 StateManager 单例"""

    @pytest.fixture(autouse=True)
    def reset(self):
        """每个测试前重置单例"""
        reset_state_manager()
        yield
        reset_state_manager()

    def test_get_state_manager(self, tmp_path: Path) -> None:
        """测试获取单例"""
        (tmp_path / "pyproject.toml").touch()
        manager = get_state_manager(tmp_path)

        assert manager is not None
        assert manager.project_root == tmp_path

    def test_singleton_reuse(self, tmp_path: Path) -> None:
        """测试单例复用"""
        (tmp_path / "pyproject.toml").touch()
        manager1 = get_state_manager(tmp_path)
        manager2 = get_state_manager()

        assert manager1 is manager2

    def test_reset_state_manager(self, tmp_path: Path) -> None:
        """测试重置单例"""
        (tmp_path / "pyproject.toml").touch()
        manager1 = get_state_manager(tmp_path)
        reset_state_manager()
        manager2 = get_state_manager(tmp_path)

        assert manager1 is not manager2
