"""
Memory Anchor MCP Server - 供 Claude Code 使用的记忆接口

基于 docs/MEMORY_STRATEGY.md 的 MCP 设计：
- memory://search - 搜索患者记忆
- memory://add - 添加记忆（仅fact层，需置信度）
- memory://constitution - 获取宪法层

使用方式：
1. 在 Claude Code 的 MCP 配置中添加此服务器
2. Claude Code 可通过 mcp__memory-anchor__* 工具访问记忆系统
"""

import asyncio
from typing import Any, Sequence
from uuid import UUID

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from backend.models.constitution_change import (
    ChangeType,
    ConstitutionProposeRequest,
)
from backend.models.note import MemoryLayer, NoteCategory
from backend.services.constitution import get_constitution_service
from backend.services.memory import (
    MemoryAddRequest,
    MemorySearchRequest,
    MemoryService,
    MemorySource,
    get_memory_service,
)

# 创建 MCP Server
server = Server("memory-anchor")


# === Tools ===


@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    return [
        Tool(
            name="search_memory",
            description="""搜索患者记忆。

⚠️ **强制调用场景**：在回答任何与以下内容相关的问题之前，必须先调用此工具：

**患者相关（照护场景）**：
- 患者身份、家人、联系方式
- 历史事件、去过的地方、见过的人
- 用药、医疗、健康相关
- 日常习惯、偏好、禁忌

**项目开发相关（开发场景）**：
- 项目历史、之前做过什么
- 设计决策、架构选型的原因
- Bug 修复记录、踩过的坑
- 上下文、背景信息
- "上次我们讨论的..."、"之前决定的..."

**核心规则**：如果当前任务不是"完全新东西"，就必须先调用此工具。
不确定时，宁可多查一次，也不要漏掉重要上下文。

**输入**：用户问题的简短概述（自然语言）
**输出**：若干条相关记忆（宪法/事实/会话层），供你引用回答问题

三层记忆说明：
- 🔴 宪法层：核心身份（始终返回，不可遗漏）
- 🔵 事实层：长期记忆（经过验证的事实）
- 🟢 会话层：短期对话记忆（24h内）

示例查询：
- "女儿电话" → 返回联系人信息
- "search_memory Bug" → 返回相关 Bug 修复记录
- "Qdrant 决策" → 返回技术选型原因
- "上次讨论的架构" → 返回设计决策""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，支持自然语言",
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["constitution", "fact", "session"],
                        "description": "过滤记忆层级（可选）",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["person", "place", "event", "item", "routine"],
                        "description": "过滤分类（可选）",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                        "description": "返回数量限制",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="add_memory",
            description="""添加记忆到系统。

注意：
- 宪法层不允许通过此工具添加（需专用流程）
- AI提取的记忆需提供置信度，会按规则处理：
  - ≥0.9: 直接存入
  - 0.7-0.9: 待确认
  - <0.7: 拒绝

示例：
- 添加患者自述："患者说今天见了老朋友张三"
- 记录观察："患者表现出对花园的喜爱" """,
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "记忆内容",
                        "minLength": 1,
                        "maxLength": 2000,
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["fact", "session"],
                        "default": "fact",
                        "description": "记忆层级（不允许constitution）",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["person", "place", "event", "item", "routine"],
                        "description": "分类（可选）",
                    },
                    "confidence": {
                        "type": "number",
                        "default": 0.8,
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "置信度（AI提取时必填）",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="get_constitution",
            description="""获取患者的全部宪法层记忆。

宪法层包含患者的核心身份信息：
- 姓名、年龄、住址
- 关键家庭成员和联系方式
- 必要的医疗信息（用药、过敏）

这些信息始终全量返回，不依赖检索。
每次对话开始时应调用此工具加载上下文。""",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="propose_constitution_change",
            description="""提议修改宪法层记忆（需三次审批）。

⚠️ **强制规则**：宪法层的任何修改，必须通过此工具提议，不得直接编辑。

三次审批流程：
1. 调用此工具 → 创建 pending 状态的变更提议
2. 照护者审批 3 次 → approvals_count 达到 3
3. 自动应用变更 → 写入宪法层

**何时使用**：
- 修改患者核心身份（姓名、住址）
- 更新联系人信息
- 修改医疗信息（用药、过敏）
- 删除错误的宪法层条目

**重要**：仅用于提议，不会立即生效。需要照护者多次确认。""",
            inputSchema={
                "type": "object",
                "properties": {
                    "change_type": {
                        "type": "string",
                        "enum": ["create", "update", "delete"],
                        "default": "create",
                        "description": "变更类型：create=新增, update=修改, delete=删除",
                    },
                    "proposed_content": {
                        "type": "string",
                        "description": "提议的内容（新增或修改后的内容）",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                    "reason": {
                        "type": "string",
                        "description": "变更理由（必填，说明为什么要修改）",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "target_id": {
                        "type": "string",
                        "description": "目标条目ID（update/delete时必填）",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["person", "place", "event", "item", "routine"],
                        "description": "分类（可选）",
                    },
                },
                "required": ["proposed_content", "reason"],
            },
        ),
        Tool(
            name="sync_to_files",
            description="""将 Qdrant 中的记忆同步到 .memos/ 文件（人类可读备份）。

**用途**：
- 将 Qdrant 中的记忆导出为 Markdown 文件
- 便于人类阅读和版本控制
- 作为 MCP 离线时的回退数据源

**同步目标**：
- .memos/fact.md - 事实层记忆
- .memos/session.md - 会话层记忆
- .memos/index.md - 记忆索引

**触发时机**：
- 会话结束时自动调用
- 用户说"同步记忆"时手动调用""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "项目路径（默认当前目录）",
                    },
                    "layers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["fact", "session"]},
                        "description": "要同步的层级（默认全部）",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """执行工具调用"""
    service = get_memory_service()

    if name == "search_memory":
        return await _handle_search_memory(service, arguments)
    elif name == "add_memory":
        return await _handle_add_memory(service, arguments)
    elif name == "get_constitution":
        return await _handle_get_constitution(service)
    elif name == "propose_constitution_change":
        return await _handle_propose_constitution_change(arguments)
    elif name == "sync_to_files":
        return await _handle_sync_to_files(arguments)
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]


async def _handle_search_memory(
    service: MemoryService, arguments: dict
) -> Sequence[TextContent]:
    """处理搜索记忆请求"""
    query = arguments.get("query", "")
    layer = arguments.get("layer")
    category = arguments.get("category")
    limit = arguments.get("limit", 5)

    request = MemorySearchRequest(
        query=query,
        layer=MemoryLayer(layer) if layer else None,
        category=NoteCategory(category) if category else None,
        include_constitution=True,
        limit=limit,
        min_score=0.3,
    )

    results = await service.search_memory(request)

    # 格式化输出
    output_lines = [f"🔍 搜索 \"{query}\" 返回 {len(results)} 条结果：\n"]

    for i, r in enumerate(results, 1):
        layer_icon = {"constitution": "🔴", "fact": "🔵", "session": "🟢"}.get(
            r.layer.value, "⚪"
        )
        constitution_mark = " [核心]" if r.is_constitution else ""
        output_lines.append(
            f"{i}. {layer_icon} [{r.layer.value}]{constitution_mark} (相关度: {r.score:.2f})"
        )
        output_lines.append(f"   {r.content}\n")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def _handle_add_memory(
    service: MemoryService, arguments: dict
) -> Sequence[TextContent]:
    """处理添加记忆请求"""
    content = arguments.get("content", "")
    layer = arguments.get("layer", "fact")
    category = arguments.get("category")
    confidence = arguments.get("confidence", 0.8)

    # 检查宪法层
    if layer == "constitution":
        return [
            TextContent(
                type="text",
                text="❌ 错误：宪法层记忆不允许通过此工具添加。请使用照护者端专用流程。",
            )
        ]

    try:
        request = MemoryAddRequest(
            content=content,
            layer=MemoryLayer(layer),
            category=NoteCategory(category) if category else None,
            source=MemorySource.AI_EXTRACTION,  # MCP 调用视为 AI 提取
            confidence=confidence,
        )

        result = await service.add_memory(request)

        status_icon = {
            "saved": "✅",
            "pending_approval": "⏳",
            "rejected_low_confidence": "❌",
        }.get(result["status"], "❓")

        output = f"{status_icon} 记忆添加结果：\n"
        output += f"- 状态: {result['status']}\n"
        output += f"- 层级: {result['layer']}\n"
        output += f"- 置信度: {result['confidence']}\n"

        if result.get("id"):
            output += f"- ID: {result['id']}\n"

        if result.get("requires_approval"):
            output += "- ⚠️ 需要照护者审批确认\n"

        if result.get("reason"):
            output += f"- 原因: {result['reason']}\n"

        return [TextContent(type="text", text=output)]

    except ValueError as e:
        return [TextContent(type="text", text=f"❌ 错误：{str(e)}")]


async def _handle_get_constitution(service: MemoryService) -> Sequence[TextContent]:
    """处理获取宪法层请求"""
    results = await service.get_constitution()

    if not results:
        return [
            TextContent(
                type="text",
                text="📋 宪法层为空。请让照护者先添加患者的核心身份信息。",
            )
        ]

    output_lines = [f"🔴 宪法层记忆（共 {len(results)} 条核心信息）：\n"]

    for i, r in enumerate(results, 1):
        category_name = r.category.value if r.category else "未分类"
        output_lines.append(f"{i}. [{category_name}] {r.content}\n")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def _handle_propose_constitution_change(arguments: dict) -> Sequence[TextContent]:
    """处理提议宪法层变更请求"""

    change_type_str = arguments.get("change_type", "create")
    proposed_content = arguments.get("proposed_content", "")
    reason = arguments.get("reason", "")
    target_id_str = arguments.get("target_id")
    category = arguments.get("category")

    if not proposed_content:
        return [TextContent(type="text", text="❌ 错误：proposed_content 是必填项")]

    if not reason:
        return [TextContent(type="text", text="❌ 错误：reason 是必填项，请说明变更理由")]

    try:
        change_type = ChangeType(change_type_str)
    except ValueError:
        return [TextContent(type="text", text=f"❌ 错误：无效的 change_type: {change_type_str}")]

    # 验证 update/delete 必须有 target_id
    if change_type in (ChangeType.UPDATE, ChangeType.DELETE) and not target_id_str:
        return [
            TextContent(
                type="text",
                text=f"❌ 错误：{change_type.value} 操作必须提供 target_id",
            )
        ]

    try:
        request = ConstitutionProposeRequest(
            change_type=change_type,
            proposed_content=proposed_content,
            reason=reason,
            target_id=UUID(target_id_str) if target_id_str else None,
            category=category,
        )

        constitution_service = get_constitution_service()
        result = await constitution_service.propose(request, proposer="claude-code")

        output = "✅ 宪法变更提议已创建\n\n"
        output += "📋 变更详情：\n"
        output += f"- ID: {result.id}\n"
        output += f"- 类型: {result.change_type.value}\n"
        output += f"- 内容: {result.proposed_content}\n"
        output += f"- 理由: {result.reason}\n"
        output += f"- 状态: {result.status.value}\n"
        output += f"- 审批进度: {result.approvals_count}/{result.approvals_needed}\n"
        output += "\n"
        output += "⏳ 下一步：需要照护者审批 3 次才能生效。\n"
        output += f"   调用 POST /api/v1/constitution/approve/{result.id} 进行审批。"

        return [TextContent(type="text", text=output)]

    except ValueError as e:
        return [TextContent(type="text", text=f"❌ 错误：{str(e)}")]


async def _handle_sync_to_files(arguments: dict) -> Sequence[TextContent]:
    """处理同步到文件请求 - 将 Qdrant 记忆导出到 .memos/ 目录"""
    import os
    from datetime import datetime
    from pathlib import Path

    from backend.services.search import get_search_service

    project_path = arguments.get("project_path") or os.getcwd()
    layers = arguments.get("layers") or ["fact", "session"]

    # 确保是列表
    if isinstance(layers, str):
        layers = [layers]

    memos_dir = Path(project_path) / ".memos"

    try:
        # 确保 .memos 目录存在
        memos_dir.mkdir(parents=True, exist_ok=True)

        search_service = get_search_service()
        sync_stats = {"fact": 0, "session": 0}
        all_notes = []

        # 获取各层记忆
        for layer in layers:
            notes = search_service.list_notes(layer=layer, limit=500)
            sync_stats[layer] = len(notes)
            all_notes.extend(notes)

        # 同步时间戳
        sync_time = datetime.now().isoformat()

        # 写入 fact.md
        if "fact" in layers:
            fact_notes = [n for n in all_notes if n.get("layer") == "fact"]
            fact_content = _format_notes_markdown(fact_notes, "事实层记忆", sync_time)
            (memos_dir / "fact.md").write_text(fact_content, encoding="utf-8")

        # 写入 session.md
        if "session" in layers:
            session_notes = [n for n in all_notes if n.get("layer") == "session"]
            session_content = _format_notes_markdown(session_notes, "会话层记忆", sync_time)
            (memos_dir / "session.md").write_text(session_content, encoding="utf-8")

        # 写入 index.md（索引）
        index_content = _format_index_markdown(all_notes, sync_time)
        (memos_dir / "index.md").write_text(index_content, encoding="utf-8")

        # 构建输出
        output = "✅ 记忆同步完成\n\n"
        output += f"📂 目标目录: {memos_dir}\n"
        output += f"⏰ 同步时间: {sync_time}\n\n"
        output += "📊 统计:\n"
        for layer in layers:
            output += f"  - {layer}: {sync_stats.get(layer, 0)} 条\n"
        output += "\n📄 生成文件:\n"
        if "fact" in layers:
            output += "  - fact.md\n"
        if "session" in layers:
            output += "  - session.md\n"
        output += "  - index.md\n"

        return [TextContent(type="text", text=output)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 同步失败: {str(e)}")]


def _format_notes_markdown(notes: list, title: str, sync_time: str) -> str:
    """格式化记忆为 Markdown"""
    lines = [
        f"# {title}",
        "",
        f"> 同步时间: {sync_time}",
        f"> 记录数: {len(notes)}",
        "",
        "---",
        "",
    ]

    if not notes:
        lines.append("*暂无记录*")
        return "\n".join(lines)

    # 按类别分组
    by_category: dict = {}
    for note in notes:
        cat = note.get("category") or "未分类"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(note)

    for category, cat_notes in sorted(by_category.items()):
        lines.append(f"## {category}")
        lines.append("")
        for note in cat_notes:
            content = note.get("content", "")
            confidence = note.get("confidence")
            source = note.get("source")
            created_at = note.get("created_at", "")

            lines.append(f"- {content}")
            meta_parts = []
            if confidence:
                meta_parts.append(f"置信度: {confidence:.2f}")
            if source:
                meta_parts.append(f"来源: {source}")
            if created_at:
                meta_parts.append(f"创建: {created_at[:10]}")
            if meta_parts:
                lines.append(f"  - *{' | '.join(meta_parts)}*")
            lines.append("")
        lines.append("")

    return "\n".join(lines)


def _format_index_markdown(notes: list, sync_time: str) -> str:
    """格式化记忆索引"""
    lines = [
        "# Memory Anchor 索引",
        "",
        f"> 同步时间: {sync_time}",
        "",
        "---",
        "",
        "## 统计",
        "",
    ]

    # 统计
    layer_count: dict = {}
    category_count: dict = {}
    for note in notes:
        layer = note.get("layer") or "unknown"
        category = note.get("category") or "未分类"
        layer_count[layer] = layer_count.get(layer, 0) + 1
        category_count[category] = category_count.get(category, 0) + 1

    lines.append("### 按层级")
    lines.append("")
    for layer, count in sorted(layer_count.items()):
        icon = {"constitution": "🔴", "fact": "🔵", "session": "🟢"}.get(layer, "⚪")
        lines.append(f"- {icon} {layer}: {count} 条")
    lines.append("")

    lines.append("### 按类别")
    lines.append("")
    for category, count in sorted(category_count.items()):
        lines.append(f"- {category}: {count} 条")
    lines.append("")

    lines.append("## 文件")
    lines.append("")
    lines.append("- [fact.md](./fact.md) - 事实层记忆")
    lines.append("- [session.md](./session.md) - 会话层记忆")
    lines.append("")

    return "\n".join(lines)


# === Resources ===


@server.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用资源"""
    return [
        Resource(
            uri="memory://constitution",
            name="患者宪法层记忆",
            description="患者的核心身份信息，包括姓名、家人、用药等",
            mimeType="text/plain",
        ),
        Resource(
            uri="memory://recent",
            name="最近记忆",
            description="最近添加的记忆（会话层 + 近期事实层）",
            mimeType="text/plain",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """读取资源内容"""
    service = get_memory_service()

    if uri == "memory://constitution":
        results = await service.get_constitution()
        if not results:
            return "宪法层为空"
        return "\n".join([f"- {r.content}" for r in results])

    elif uri == "memory://recent":
        # 搜索最近的记忆（使用通用关键词搜索全部）
        request = MemorySearchRequest(
            query="记忆",  # 使用通用关键词
            include_constitution=False,
            limit=10,
            min_score=0.0,  # 不过滤分数，返回所有匹配
        )
        results = await service.search_memory(request)
        if not results:
            return "暂无最近记忆"
        return "\n".join([f"[{r.layer.value}] {r.content}" for r in results])

    return f"未知资源: {uri}"


# === Main ===


async def main():
    """启动 MCP Server"""
    # 重置所有单例以确保使用最新的环境变量（MCP_MEMORY_PROJECT_ID）
    from backend.config import reset_config
    from backend.services.search import reset_search_service
    from backend.services.memory import reset_memory_service

    reset_config()
    reset_search_service()
    reset_memory_service()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
