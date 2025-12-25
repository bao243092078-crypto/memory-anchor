"""
Memory Anchor State Management - 状态文件管理

提供项目级别的结构化状态文件管理：
1. `.claude/state/session.json` - 会话元数据
2. `.claude/state/test-recommendation.json` - 测试建议
3. `.claude/state/session-history/` - 历史会话记录

用法：
    from backend.state import StateManager

    # 初始化（自动检测项目根目录）
    state = StateManager()

    # 或指定项目路径
    state = StateManager(project_root="/path/to/project")

    # 保存会话状态
    state.save_session(session_id="abc", modified_files=[...])

    # 获取测试建议
    recommendations = state.get_test_recommendations()
"""

from backend.state.manager import (
    StateManager,
    get_state_manager,
    reset_state_manager,
)
from backend.state.models import (
    SessionState,
    TestRecommendation,
)

__all__ = [
    "StateManager",
    "get_state_manager",
    "reset_state_manager",
    "SessionState",
    "TestRecommendation",
]
