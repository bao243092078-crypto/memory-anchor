# Memory Anchor Viewer

Memory Anchor 的 Web UI 前端，用于浏览、搜索和管理 AI 记忆。

## 技术栈

- React 18 + TypeScript
- Vite (构建工具)
- Tailwind CSS (样式)

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

默认访问地址：http://localhost:5173

## 功能

### Phase 1: 基础浏览
- 语义搜索记忆
- 层级筛选 (L0-L4)
- 分类筛选 (人物/地点/事件/物品/习惯)
- 记忆卡片展示

### Phase 2: 快速操作
- 快速验证 (✓) - 一键将 AI 提取的记忆置信度提升至 100%
- 安全删除 (✗) - 需二次确认的删除操作
- 详情弹窗 - 完整信息 + JSON 原始数据

### 规划中
- Phase 3: 内容编辑
- Phase 4: 关联信息编辑

## 组件结构

```
src/
├── components/
│   ├── Header.tsx        # 顶部导航
│   ├── SearchBar.tsx     # 搜索框
│   ├── FilterPanel.tsx   # 左侧筛选面板
│   ├── MemoryCard.tsx    # 记忆卡片
│   ├── MemoryList.tsx    # 记忆列表
│   ├── MemoryDetail.tsx  # 详情弹窗
│   ├── JsonViewer.tsx    # JSON 查看器
│   └── ConfirmDialog.tsx # 确认弹窗
├── hooks/
│   ├── useMemories.ts    # 记忆数据 Hook
│   └── useMemoryActions.ts # 操作 Hook (验证/删除)
├── api/
│   └── memory.ts         # API 客户端
├── types/
│   └── index.ts          # TypeScript 类型定义
└── App.tsx               # 主应用
```

## 设计规范

- 极简黑白配色 + 亮绿色强调色 (#84CC16)
- 大量留白，现代 SaaS 风格
- Inter 字体
- 圆角设计 (rounded-xl, rounded-2xl)

## API 依赖

需要后端服务运行在 http://localhost:8000，主要接口：

- `GET /api/v1/notes` - 获取记忆列表
- `POST /api/v1/search` - 语义搜索
- `PUT /api/v1/notes/{id}` - 更新记忆
- `DELETE /api/v1/notes/{id}` - 删除记忆
- `POST /api/v1/notes/{id}/verify` - 验证记忆

## 环境变量

在 `.env.local` 中配置：

```env
VITE_API_BASE_URL=http://localhost:8000
```
