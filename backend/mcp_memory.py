"""
Memory Anchor MCP Server v2.0 - 供 Claude Code 使用的记忆接口

基于 docs/MEMORY_STRATEGY.md 的五层认知记忆模型：
- L0: identity_schema (自我概念) - 核心身份，三次审批
- L1: active_context (工作记忆) - 会话临时状态，不持久化
- L2: event_log (情景记忆) - 带时空标记的事件
- L3: verified_fact (语义记忆) - 验证过的长期事实
- L4: operational_knowledge (技能图式) - 操作性知识

MCP 工具：
- search_memory - 搜索患者记忆
- add_memory - 添加记忆（L2/L3 层）
- get_constitution - 获取宪法层（L0）
- log_event - 记录事件到情景记忆（L2）
- search_events - 搜索事件日志
- promote_to_fact - 将事件提升为事实（L2 → L3）

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

from backend.models.checklist import (
    ChecklistBriefingRequest,
    ChecklistItemCreate,
    ChecklistPriority,
    ChecklistScope,
    PlanSyncRequest,
)
from backend.models.constitution_change import (
    ChangeType,
    ConstitutionProposeRequest,
)
from backend.models.note import MemoryLayer, NoteCategory
from backend.services.checklist_service import get_checklist_service
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
                        "enum": [
                            "identity_schema",
                            "event_log",
                            "verified_fact",
                            "constitution",
                            "fact",
                            "session",
                        ],
                        "description": "过滤记忆层级（可选）。新术语：identity_schema/event_log/verified_fact；旧术语（兼容）：constitution/fact/session",
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
                        "enum": [
                            "verified_fact",
                            "event_log",
                            "fact",
                            "session",
                        ],
                        "default": "verified_fact",
                        "description": "记忆层级。推荐：verified_fact（L3）或 event_log（L2）。旧术语 fact/session 仍兼容。不允许 identity_schema/constitution",
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
            name="delete_memory",
            description="""删除指定的记忆。

🔴 **高风险操作** - 需要用户明确确认。

调用此工具前，请确保：
1. 用户在消息中包含确认短语：
   - "确认删除" / "我确认"
   - "confirm delete" / "I confirm"
2. 已向用户说明将要删除的内容

如果没有确认短语，操作将被拦截。

**使用场景**：
- 清理错误添加的记忆
- 删除过时的信息
- 患者/照护者要求删除

**注意**：
- 不允许删除宪法层记忆（需使用 propose_constitution_change）
- 删除操作不可逆
- 建议先 search_memory 确认要删除的内容""",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "要删除的记忆 ID（UUID）",
                    },
                    "confirmation": {
                        "type": "string",
                        "description": "确认短语（必须包含 '确认删除' 或 'confirm delete'）",
                    },
                },
                "required": ["note_id", "confirmation"],
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
                        "items": {
                            "type": "string",
                            "enum": [
                                "verified_fact",
                                "event_log",
                                "fact",
                                "session",
                            ],
                        },
                        "description": "要同步的层级（默认全部）。新术语：verified_fact/event_log；旧术语：fact/session",
                    },
                },
            },
        ),
        # ===== L2 Event Log 工具（五层模型新增）=====
        Tool(
            name="log_event",
            description="""记录事件到情景记忆（L2 event_log）。

情景记忆的核心特征（来自认知科学）：
- **when**：事件发生时间
- **where**：事件发生地点
- **who**：涉及的人物

**用途**：
- 记录患者的日常活动
- 记录项目开发中的重要事件
- 记录 Bug 修复、功能完成等里程碑

**与 add_memory 的区别**：
- log_event 专门用于带时空标记的事件（L2）
- add_memory 用于通用记忆（L3 verified_fact）

**示例**：
- "患者今天下午在花园散步，遇到了老朋友张三"
- "修复了 search_memory 空查询的 Bug"
- "完成了五层记忆模型的 MCP 工具添加" """,
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "事件内容描述",
                        "minLength": 1,
                        "maxLength": 2000,
                    },
                    "when": {
                        "type": "string",
                        "format": "date-time",
                        "description": "事件发生时间（ISO 8601格式，默认当前时间）",
                    },
                    "where": {
                        "type": "string",
                        "description": "事件发生地点（可选）",
                        "maxLength": 200,
                    },
                    "who": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "涉及的人物列表（可选）",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["person", "place", "event", "item", "routine"],
                        "description": "事件分类（可选）",
                    },
                    "ttl_days": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "存活天数（可选，默认永久）",
                    },
                    "confidence": {
                        "type": "number",
                        "default": 0.8,
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "置信度",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="search_events",
            description="""搜索事件日志（L2 event_log）。

支持多维度过滤：
- **时间范围**：start_time / end_time
- **地点**：where
- **人物**：who
- **语义搜索**：query

**与 search_memory 的区别**：
- search_events 专门搜索 L2 event_log，支持时间范围
- search_memory 搜索所有层级的记忆

**示例查询**：
- 搜索上周的所有事件
- 搜索发生在"花园"的事件
- 搜索涉及"张三"的事件""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询（可选，留空返回最近事件）",
                    },
                    "start_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "开始时间（ISO 8601格式）",
                    },
                    "end_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "结束时间（ISO 8601格式）",
                    },
                    "where": {
                        "type": "string",
                        "description": "地点过滤",
                    },
                    "who": {
                        "type": "string",
                        "description": "人物过滤（涉及此人的事件）",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                        "description": "返回数量限制",
                    },
                },
            },
        ),
        Tool(
            name="promote_to_fact",
            description="""将事件提升为验证事实（L2 → L3）。

当一个事件经过验证，可以从情景记忆（L2 event_log）提升为语义记忆（L3 verified_fact）。

**何时使用**：
- 事件被照护者/用户确认为真实
- 临时发现需要转为长期记忆
- 重复出现的事件需要固化

**提升后的变化**：
- 从 event_log 层移动到 verified_fact 层
- 不再受 TTL 限制（永久保留）
- 标记 verified_by 和 promoted_at

**示例**：
- 将"患者今天认出了女儿"提升为事实
- 将"发现 Qdrant 不支持并发"提升为长期记录""",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "要提升的事件 ID（UUID）",
                    },
                    "verified_by": {
                        "type": "string",
                        "default": "caregiver",
                        "description": "验证者（默认 caregiver）",
                    },
                    "notes": {
                        "type": "string",
                        "description": "提升备注（可选）",
                    },
                },
                "required": ["event_id"],
            },
        ),
        # ===== Checklist 工具（清单革命 - 与 Plan skill 协同）=====
        Tool(
            name="get_checklist_briefing",
            description="""获取清单简报（会话开始时调用）。

**核心理念**（来自《清单革命》+ 三方 AI 头脑风暴）：
- Checklist = 战略层（跨会话持久）
- Plan skill = 战术层（单次任务）
- 通过 (ma:xxx) ID 机制连接两者

**何时调用**：
- SessionStart 时获取待办清单
- 上下文压缩后恢复工作状态
- 用户说"我在做什么来着？"

**返回格式**：
Markdown 格式的清单简报，按优先级分组，包含 (ma:xxx) 引用 ID。

**与 Plan skill 的关系**：
- 先调用 get_checklist_briefing 获取战略约束
- 再使用 Plan skill 生成当前任务的具体步骤
- 完成后调用 sync_plan_to_checklist 同步状态""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "项目 ID",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["project", "repo", "global"],
                        "description": "作用域过滤（可选）",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 12,
                        "minimum": 1,
                        "maximum": 50,
                        "description": "返回数量限制",
                    },
                    "include_ids": {
                        "type": "boolean",
                        "default": True,
                        "description": "是否包含 (ma:xxx) ID（供 Plan skill 引用）",
                    },
                },
                "required": ["project_id"],
            },
        ),
        Tool(
            name="sync_plan_to_checklist",
            description="""从 Plan 同步清单状态（SessionEnd 时调用）。

**解析 plan.md 内容**：
1. 找到 [x] 的项目，如果有 (ma:xxx) 引用则标记对应清单项完成
2. 找到 @persist 标签的项目，创建新的清单项
3. 返回同步结果

**何时调用**：
- SessionEnd 时同步 Plan 执行结果
- 用户说"存进度"、"同步清单"

**示例 plan.md 内容**：
```
- [x] 修复 QDRANT_URL 问题 (ma:abc12345)
- [ ] 实现 ChecklistService @persist
- [x] 添加 MCP 工具 (ma:def67890)
```

**同步结果**：
- (ma:abc12345) 和 (ma:def67890) 标记为完成
- "实现 ChecklistService" 创建为新清单项""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "项目 ID",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID（用于标记来源）",
                    },
                    "plan_markdown": {
                        "type": "string",
                        "description": "plan.md 内容",
                    },
                },
                "required": ["project_id", "session_id", "plan_markdown"],
            },
        ),
        Tool(
            name="create_checklist_item",
            description="""创建清单项。

用于手动创建跨会话持久的清单项。

**与 add_memory 的区别**：
- add_memory: 添加记忆（被动存储）
- create_checklist_item: 创建待办（主动跟踪）

**优先级**：
- 1 (critical): 🔴 紧急
- 2 (high): 🟠 高优
- 3 (normal): 🟡 普通
- 4 (low): 🟢 低优
- 5 (backlog): ⚪ 待定

**示例**：
- 创建一个高优先级的 Bug 修复任务
- 创建一个普通的功能开发任务""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "项目 ID",
                    },
                    "content": {
                        "type": "string",
                        "description": "清单内容",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4, 5],
                        "default": 3,
                        "description": "优先级（1=紧急, 2=高, 3=普通, 4=低, 5=待定）",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["project", "repo", "global"],
                        "default": "project",
                        "description": "作用域",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表",
                    },
                    "ttl_days": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "存活天数（可选）",
                    },
                },
                "required": ["project_id", "content"],
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
    elif name == "delete_memory":
        return await _handle_delete_memory(arguments)
    elif name == "sync_to_files":
        return await _handle_sync_to_files(arguments)
    # ===== L2 Event Log 工具（五层模型新增）=====
    elif name == "log_event":
        return await _handle_log_event(arguments)
    elif name == "search_events":
        return await _handle_search_events(arguments)
    elif name == "promote_to_fact":
        return await _handle_promote_to_fact(arguments)
    # ===== Checklist 工具（清单革命）=====
    elif name == "get_checklist_briefing":
        return await _handle_get_checklist_briefing(arguments)
    elif name == "sync_plan_to_checklist":
        return await _handle_sync_plan_to_checklist(arguments)
    elif name == "create_checklist_item":
        return await _handle_create_checklist_item(arguments)
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
        layer=MemoryLayer.from_string(layer) if layer else None,
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
    layer = arguments.get("layer", "verified_fact")  # 默认使用新术语
    category = arguments.get("category")
    confidence = arguments.get("confidence", 0.8)

    # 检查宪法层（新旧术语都要阻止）
    if layer in ("constitution", "identity_schema"):
        return [
            TextContent(
                type="text",
                text="❌ 错误：宪法层（identity_schema）记忆不允许通过此工具添加。请使用 propose_constitution_change 工具。",
            )
        ]

    try:
        request = MemoryAddRequest(
            content=content,
            layer=MemoryLayer.from_string(layer),
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


async def _handle_delete_memory(arguments: dict) -> Sequence[TextContent]:
    """
    处理删除记忆请求 - 高风险操作，需要用户确认。

    使用 Gating Hook 机制拦截危险操作。
    """
    from uuid import UUID

    from backend.hooks.gating_hook import gate_operation, is_confirmation_present
    from backend.services.search import get_search_service

    note_id = arguments.get("note_id", "")
    confirmation = arguments.get("confirmation", "")

    # Step 1: 验证 note_id 格式
    if not note_id:
        return [TextContent(type="text", text="❌ 错误：note_id 是必填项")]

    try:
        note_uuid = UUID(note_id)
    except ValueError:
        return [
            TextContent(type="text", text=f"❌ 错误：无效的 note_id 格式: {note_id}")
        ]

    # Step 2: 调用 Gating Hook 检查确认短语
    gate_result = gate_operation(
        tool_name="delete_memory",
        arguments={"note_id": note_id},
        user_message=confirmation,
    )

    if not gate_result["allowed"]:
        # 操作被拦截，返回确认消息
        output = gate_result.get("confirmation_message") or gate_result.get("reason") or "操作被拦截"
        return [TextContent(type="text", text=output)]

    # Step 3: 执行删除
    try:
        search_service = get_search_service()

        # 先检查记忆是否存在
        existing = search_service.get_note(note_uuid)
        if not existing:
            return [
                TextContent(
                    type="text",
                    text=f"❌ 错误：未找到 ID 为 {note_id} 的记忆",
                )
            ]

        # 检查是否是宪法层（禁止直接删除）
        layer = existing.get("layer", "")
        if layer and layer.lower() in ("constitution", "identity_schema"):
            return [
                TextContent(
                    type="text",
                    text="❌ 错误：无法直接删除宪法层记忆。请使用 propose_constitution_change 工具提议删除。",
                )
            ]

        # 执行删除
        success = search_service.delete_note(note_uuid)

        if success:
            content = existing.get("content", "")
            output = "✅ 记忆已删除\n\n"
            output += f"- ID: {note_id}\n"
            output += f"- 内容: {content[:100]}{'...' if len(content) > 100 else ''}\n"
            output += f"- 层级: {layer}\n"
            output += "\n⚠️ 此操作不可逆。"
            return [TextContent(type="text", text=output)]
        else:
            return [TextContent(type="text", text="❌ 删除失败：未知错误")]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 删除失败：{str(e)}")]


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


# ===== L2 Event Log 处理函数（五层模型新增）=====


async def _handle_log_event(arguments: dict) -> Sequence[TextContent]:
    """处理记录事件请求（L2 event_log）"""
    from datetime import datetime

    from backend.core.memory_kernel import get_memory_kernel

    content = arguments.get("content", "")
    when_str = arguments.get("when")
    where = arguments.get("where")
    who = arguments.get("who", [])
    category = arguments.get("category")
    ttl_days = arguments.get("ttl_days")
    confidence = arguments.get("confidence", 0.8)

    if not content:
        return [TextContent(type="text", text="❌ 错误：content 是必填项")]

    try:
        # 解析时间
        when = None
        if when_str:
            try:
                when = datetime.fromisoformat(when_str.replace("Z", "+00:00"))
            except ValueError:
                return [
                    TextContent(
                        type="text", text=f"❌ 错误：无效的时间格式: {when_str}"
                    )
                ]

        kernel = get_memory_kernel()
        result = kernel.log_event(
            content=content,
            when=when,
            where=where,
            who=who if who else None,
            category=category,
            ttl_days=ttl_days,
            confidence=confidence,
        )

        # 格式化输出
        output = "✅ 事件已记录到情景记忆（L2 event_log）\n\n"
        output += "📋 事件详情：\n"
        output += f"- ID: {result.get('id', 'N/A')}\n"
        output += f"- 内容: {content}\n"
        if result.get("when"):
            output += f"- 时间: {result['when']}\n"
        if where:
            output += f"- 地点: {where}\n"
        if who:
            output += f"- 人物: {', '.join(who)}\n"
        if category:
            output += f"- 分类: {category}\n"
        if ttl_days:
            output += f"- TTL: {ttl_days} 天\n"
        output += f"- 置信度: {confidence}\n"

        return [TextContent(type="text", text=output)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 记录事件失败: {str(e)}")]


async def _handle_search_events(arguments: dict) -> Sequence[TextContent]:
    """处理搜索事件请求（L2 event_log）"""
    from datetime import datetime

    from backend.core.memory_kernel import get_memory_kernel

    query = arguments.get("query", "")
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    where = arguments.get("where")
    who = arguments.get("who")
    limit = arguments.get("limit", 10)

    try:
        # 解析时间
        start_time = None
        end_time = None

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(
                    start_time_str.replace("Z", "+00:00")
                )
            except ValueError:
                return [
                    TextContent(
                        type="text", text=f"❌ 错误：无效的开始时间格式: {start_time_str}"
                    )
                ]

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except ValueError:
                return [
                    TextContent(
                        type="text", text=f"❌ 错误：无效的结束时间格式: {end_time_str}"
                    )
                ]

        kernel = get_memory_kernel()
        results = kernel.search_events(
            query=query,
            start_time=start_time,
            end_time=end_time,
            where=where,
            who=who,
            limit=limit,
        )

        # 格式化输出
        filter_desc = []
        if query:
            filter_desc.append(f'查询="{query}"')
        if start_time:
            filter_desc.append(f"开始={start_time_str}")
        if end_time:
            filter_desc.append(f"结束={end_time_str}")
        if where:
            filter_desc.append(f"地点={where}")
        if who:
            filter_desc.append(f"人物={who}")

        filter_str = ", ".join(filter_desc) if filter_desc else "无过滤条件"

        output = f"🔍 搜索事件日志（{filter_str}）\n"
        output += f"📊 找到 {len(results)} 条结果：\n\n"

        if not results:
            output += "*暂无匹配的事件*"
        else:
            for i, event in enumerate(results, 1):
                output += f"{i}. 🟢 [{event.get('when', 'N/A')}]\n"
                output += f"   {event.get('content', '')}\n"
                if event.get("where"):
                    output += f"   📍 地点: {event['where']}\n"
                if event.get("who"):
                    who_list = event["who"]
                    if isinstance(who_list, list):
                        output += f"   👤 人物: {', '.join(who_list)}\n"
                    else:
                        output += f"   👤 人物: {who_list}\n"
                output += f"   ID: {event.get('id', 'N/A')}\n"
                output += "\n"

        return [TextContent(type="text", text=output)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 搜索事件失败: {str(e)}")]


async def _handle_promote_to_fact(arguments: dict) -> Sequence[TextContent]:
    """处理事件提升请求（L2 → L3）"""
    from backend.core.memory_kernel import get_memory_kernel

    event_id = arguments.get("event_id", "")
    verified_by = arguments.get("verified_by", "caregiver")
    notes = arguments.get("notes")

    if not event_id:
        return [TextContent(type="text", text="❌ 错误：event_id 是必填项")]

    try:
        kernel = get_memory_kernel()
        result = kernel.promote_event_to_fact(
            event_id=event_id,
            verified_by=verified_by,
            notes=notes,
        )

        # 格式化输出
        output = "✅ 事件已提升为验证事实（L2 → L3）\n\n"
        output += "📋 提升详情：\n"
        output += f"- 原事件 ID: {event_id}\n"
        output += f"- 新事实 ID: {result.get('fact_id', 'N/A')}\n"
        output += f"- 验证者: {verified_by}\n"
        if notes:
            output += f"- 备注: {notes}\n"
        output += f"- 提升时间: {result.get('promoted_at', 'N/A')}\n"
        output += "\n"
        output += "📝 提升后的变化：\n"
        output += "- 从 event_log 层移动到 verified_fact 层\n"
        output += "- 不再受 TTL 限制（永久保留）\n"

        return [TextContent(type="text", text=output)]

    except ValueError as e:
        return [TextContent(type="text", text=f"❌ 错误：{str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ 提升事件失败: {str(e)}")]


# ===== Checklist 处理函数（清单革命）=====


async def _handle_get_checklist_briefing(arguments: dict) -> Sequence[TextContent]:
    """处理获取清单简报请求"""
    project_id = arguments.get("project_id", "")
    scope_str = arguments.get("scope")
    limit = arguments.get("limit", 12)
    include_ids = arguments.get("include_ids", True)

    if not project_id:
        return [TextContent(type="text", text="❌ 错误：project_id 是必填项")]

    try:
        scope = ChecklistScope(scope_str) if scope_str else None

        request = ChecklistBriefingRequest(
            project_id=project_id,
            scope=scope,
            limit=limit,
            include_ids=include_ids,
        )

        service = get_checklist_service()
        briefing = service.get_briefing(request)

        return [TextContent(type="text", text=briefing)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 获取清单简报失败: {str(e)}")]


async def _handle_sync_plan_to_checklist(arguments: dict) -> Sequence[TextContent]:
    """处理 Plan 同步请求"""
    project_id = arguments.get("project_id", "")
    session_id = arguments.get("session_id", "")
    plan_markdown = arguments.get("plan_markdown", "")

    if not project_id:
        return [TextContent(type="text", text="❌ 错误：project_id 是必填项")]
    if not session_id:
        return [TextContent(type="text", text="❌ 错误：session_id 是必填项")]
    if not plan_markdown:
        return [TextContent(type="text", text="❌ 错误：plan_markdown 是必填项")]

    try:
        request = PlanSyncRequest(
            project_id=project_id,
            session_id=session_id,
            plan_markdown=plan_markdown,
        )

        service = get_checklist_service()
        result = service.sync_from_plan(request)

        # 格式化输出
        output = "✅ Plan 同步完成\n\n"

        if result.completed:
            output += f"📋 标记完成 ({len(result.completed)} 项):\n"
            for short_id in result.completed:
                output += f"  - (ma:{short_id}) ✓\n"
            output += "\n"

        if result.created:
            output += f"📝 新建清单项 ({len(result.created)} 项):\n"
            for item in result.created:
                output += f"  - {item['content']} {item['ma_ref']}\n"
            output += "\n"

        if result.warnings:
            output += "⚠️ 警告:\n"
            for warning in result.warnings:
                output += f"  - {warning}\n"
            output += "\n"

        if not result.completed and not result.created:
            output += "*无变更*\n"

        return [TextContent(type="text", text=output)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ Plan 同步失败: {str(e)}")]


async def _handle_create_checklist_item(arguments: dict) -> Sequence[TextContent]:
    """处理创建清单项请求"""
    project_id = arguments.get("project_id", "")
    content = arguments.get("content", "")
    priority_int = arguments.get("priority", 3)
    scope_str = arguments.get("scope", "project")
    tags = arguments.get("tags", [])
    ttl_days = arguments.get("ttl_days")

    if not project_id:
        return [TextContent(type="text", text="❌ 错误：project_id 是必填项")]
    if not content:
        return [TextContent(type="text", text="❌ 错误：content 是必填项")]

    try:
        request = ChecklistItemCreate(
            content=content,
            priority=ChecklistPriority(priority_int),
            scope=ChecklistScope(scope_str),
            tags=tags if tags else [],
            ttl_days=ttl_days,
        )

        service = get_checklist_service()
        item = service.create_item(project_id, request)

        # 格式化输出
        priority_labels = {
            ChecklistPriority.CRITICAL: "🔴 紧急",
            ChecklistPriority.HIGH: "🟠 高优",
            ChecklistPriority.NORMAL: "🟡 普通",
            ChecklistPriority.LOW: "🟢 低优",
            ChecklistPriority.BACKLOG: "⚪ 待定",
        }

        output = "✅ 清单项已创建\n\n"
        output += "📋 详情:\n"
        output += f"- 内容: {item.content}\n"
        output += f"- ID: {item.id}\n"
        output += f"- 引用: {item.ma_ref()}\n"
        output += f"- 优先级: {priority_labels.get(item.priority, '未知')}\n"
        output += f"- 作用域: {item.scope.value}\n"
        if item.tags:
            output += f"- 标签: {', '.join(item.tags)}\n"
        if item.expires_at:
            output += f"- 过期时间: {item.expires_at.isoformat()}\n"

        return [TextContent(type="text", text=output)]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 创建清单项失败: {str(e)}")]


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
    from backend.services.checklist_service import reset_checklist_service
    from backend.services.memory import reset_memory_service
    from backend.services.search import reset_search_service

    reset_config()
    reset_search_service()
    reset_memory_service()
    reset_checklist_service()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
