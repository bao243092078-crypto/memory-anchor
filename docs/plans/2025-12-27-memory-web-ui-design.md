# Memory Anchor Web UI 设计文档

> 日期：2025-12-27
> 状态：已完成

## 背景

用户需要一个 Web 界面来浏览和搜索 Memory Anchor 中的记忆，类似于：
- **Claude-Mem** 的 Web Viewer (localhost:37777)
- **OpenCode** 的内置 webui

### 竞品调研结果

**Claude-Mem Web Viewer:**
- 标签页导航：STATIC, DAILY, STATS, CONFIG, FILES, RULES, PLUGINS, LOGS
- 左侧边栏：搜索 + 树形导航
- 右侧面板：内容展示
- FTS5 全文搜索
- React 实现 (src/ui/viewer/)

**OpenCode WebUI:**
- Terminal TUI + Web 双模式
- 通过 SDK 暴露 Web 端口
- 支持远程 sandbox 连接

## 用户选择

| 维度 | 选择 |
|------|------|
| 功能范围 | A) 仅查看（搜索、浏览、筛选） |
| 技术栈 | A) React + Tailwind（复用现有 frontend/） |
| 启动方式 | C) CLI 启动临时服务 `./ma web` |

## 设计方案

### 核心功能

1. **记忆列表浏览**
   - 按时间倒序显示
   - 支持按 layer 筛选（L0-L4）
   - 支持按 category 筛选（person/place/event/item/routine）

2. **语义搜索**
   - 调用现有 search_memory API
   - 显示相关度评分

3. **记忆详情**
   - 显示完整内容
   - 显示可追溯性字段：session_id, related_files（v2.1 新增）
   - 显示元数据：layer, category, confidence, created_at

### 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  Memory Anchor Viewer                        [端口: 37778]  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌───────────────────────────────────────┐ │
│  │ 筛选器      │  │ 搜索框 [________________] [搜索]      │ │
│  │             │  ├───────────────────────────────────────┤ │
│  │ Layer:      │  │                                       │ │
│  │ ○ 全部      │  │  记忆卡片列表                          │ │
│  │ ○ L0 身份   │  │  ┌─────────────────────────────────┐  │ │
│  │ ○ L2 事件   │  │  │ [verified_fact] [event]         │  │ │
│  │ ○ L3 事实   │  │  │ 修复了 search_memory 空查询问题  │  │ │
│  │ ○ L4 操作   │  │  │ session: 20251227_200000        │  │ │
│  │             │  │  │ files: backend/services/search.py│ │ │
│  │ Category:   │  │  │ 2025-12-27 20:00:00             │  │ │
│  │ □ person    │  │  └─────────────────────────────────┘  │ │
│  │ □ place     │  │                                       │ │
│  │ □ event     │  │  ┌─────────────────────────────────┐  │ │
│  │ □ item      │  │  │ [event_log] [routine]           │  │ │
│  │ □ routine   │  │  │ ...                              │  │ │
│  │             │  │  └─────────────────────────────────┘  │ │
│  └─────────────┘  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 技术架构

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  React Frontend │ ───→ │  FastAPI Backend │ ───→ │     Qdrant      │
│  (Vite + TW)    │      │  (现有 API)      │      │   (向量存储)    │
└─────────────────┘      └─────────────────┘      └─────────────────┘
         │                        │
         └────────────────────────┘
              localhost:37778
```

### CLI 命令

```bash
# 启动 Web Viewer（前后端一体）
./ma web [--port 37778] [--project 阿默斯海默症]

# 实现方式：
# 1. 启动 FastAPI 后端（复用现有 API）
# 2. 提供静态文件服务（React build 产物）
# 3. 打开浏览器
```

### 文件结构

```
frontend/
├── caregiver/          # 现有照护者界面
└── viewer/             # 新增：记忆查看器
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── MemoryCard.tsx      # 单条记忆卡片
    │   │   ├── MemoryList.tsx      # 记忆列表
    │   │   ├── SearchBar.tsx       # 搜索框
    │   │   ├── FilterPanel.tsx     # 筛选面板
    │   │   └── Header.tsx          # 顶部栏
    │   ├── hooks/
    │   │   ├── useMemories.ts      # 记忆数据 Hook
    │   │   └── useSearch.ts        # 搜索 Hook
    │   └── api/
    │       └── memory.ts           # API 调用
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    └── tailwind.config.js

backend/cli/
└── web_cmd.py          # 新增：./ma web 命令
```

### API 复用

现有 API 足够支持：

| 功能 | API | 状态 |
|------|-----|------|
| 列表 | `GET /api/v1/notes` | ✅ 已有 |
| 搜索 | `POST /api/v1/search` | ✅ 已有 |
| 详情 | `GET /api/v1/notes/{id}` | ✅ 已有 |
| 宪法层 | `GET /api/v1/constitution` | ✅ 已有 |

### 不做的事

- ❌ 不做编辑/删除功能（只读）
- ❌ 不做用户认证（本地工具）
- ❌ 不做持久化服务（临时启动）
- ❌ 不做复杂统计图表

## 工作量估算

| 模块 | 文件 | 复杂度 |
|------|------|--------|
| React 组件 | 5-6 个 | 低 |
| API 调用层 | 1 个 | 低 |
| CLI 命令 | 1 个 | 低 |
| Vite 配置 | 2 个 | 低 |

**总计**：约 10 个文件，预计可在 1 个会话内完成。

## 端口选择

- **37778**（避免与 Claude-Mem 的 37777 冲突）
- 用户可通过 `--port` 参数自定义

## 下一步

1. 确认设计方案
2. 创建 frontend/viewer/ 目录结构
3. 实现 React 组件
4. 实现 ./ma web 命令
5. 测试联调
