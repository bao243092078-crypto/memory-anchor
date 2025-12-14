"""
MemoryClient - Memory Anchor Native SDK

为 Codex 等外部 AI 提供原生 Python 接口（同步，无需 async）。

使用示例：
    from memory_anchor.sdk import MemoryClient

    client = MemoryClient()
    results = client.search_memory("女儿电话")
    for r in results:
        print(r["content"])
"""

import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.core.memory_kernel import get_memory_kernel


class MemoryClient:
    """
    Memory Anchor 原生客户端

    设计用于 Codex 等 Python 脚本直接调用，提供：
    - 同步接口（无需 await）
    - 简单易用（类似 requests 库）
    - 共享存储（与 Claude 看到同样的记忆）

    默认行为：
    - 只读访问（搜索记忆）
    - 会话层隔离（agent_id="codex"）
    - 宪法层和事实层共享
    """

    def __init__(
        self,
        agent_id: str = "codex",
        db_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """
        初始化记忆客户端

        Args:
            agent_id: Agent 标识符（用于会话层隔离）
            db_path: 数据库路径（可选，默认使用环境变量）
            project_id: 项目ID（用于多项目隔离）
        """
        self.agent_id = agent_id

        # 设置项目ID（如果提供）
        if project_id:
            os.environ["MCP_MEMORY_PROJECT_ID"] = project_id

        # 获取 MemoryKernel 实例
        self.kernel = get_memory_kernel()

    def search_memory(
        self,
        query: str,
        layer: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            query: 搜索查询（自然语言）
            layer: 过滤层级（"fact"/"session"），None=搜索全部
            limit: 返回数量限制

        Returns:
            记忆结果列表，每项包含：
            - id: UUID（字符串）
            - content: 内容
            - layer: 层级
            - score: 相关度分数
            - is_constitution: 是否为宪法层

        示例：
            results = client.search_memory("女儿电话")
            for r in results:
                print(f"[{r['layer']}] {r['content']}")
        """
        results = self.kernel.search_memory(
            query=query,
            layer=layer,
            limit=limit,
            agent_id=self.agent_id,
            include_constitution=True,
        )
        return [self._normalize_result(r) for r in results]

    def get_constitution(self) -> List[Dict[str, Any]]:
        """
        获取全部宪法层记忆

        宪法层包含患者的核心身份信息，始终全量返回。

        Returns:
            宪法层记忆列表

        示例：
            constitution = client.get_constitution()
            for item in constitution:
                print(item["content"])
        """
        return [self._normalize_result(r) for r in self.kernel.get_constitution()]

    def add_observation(
        self,
        content: str,
        layer: str = "fact",
        confidence: float = 0.8,
    ) -> Dict[str, Any]:
        """
        添加观察记录（AI 提取的记忆）

        ⚠️ 注意：置信度 < 0.9 的记录会进入待审批区，需照护者确认。

        Args:
            content: 记忆内容
            layer: 层级（"fact"/"session"）
            confidence: 置信度（0-1），建议 0.8

        Returns:
            {"id": UUID, "status": "saved"/"pending_approval", ...}

        示例：
            result = client.add_observation(
                content="患者提到明天要去看医生",
                layer="fact",
                confidence=0.85
            )
            if result["status"] == "pending_approval":
                print("需要照护者确认")
        """
        result = self.kernel.add_memory(
            content=content,
            layer=layer,
            source="external_ai",  # 标记为外部 AI
            confidence=confidence,
            agent_id=self.agent_id if layer == "session" else None,
        )
        return self._normalize_result(result)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆系统统计信息

        Returns:
            {"total_count": int, "vector_size": int, ...}
        """
        return self.kernel.get_stats()

    @staticmethod
    def _normalize_result(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将内核返回值标准化为 JSON 友好结构。

        - UUID → str
        """
        if "id" in data:
            memory_id = data.get("id")
            if isinstance(memory_id, UUID):
                data = {**data, "id": str(memory_id)}
        return data


__all__ = ["MemoryClient"]
