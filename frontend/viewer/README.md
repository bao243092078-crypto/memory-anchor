# Memory Anchor Viewer

Memory Anchor 的 Web UI 前端，用于浏览、搜索和管理 AI 记忆。

## 技术栈

- React 18 + TypeScript
- Vite (构建工具)
- Tailwind CSS (样式)
- Recharts (图表可视化)
- i18next (国际化)

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

### 基础浏览
- 语义搜索记忆
- 层级筛选 (L0-L4)
- 分类筛选 (人物/地点/事件/物品/习惯)
- 记忆卡片展示

### 快速操作
- 快速验证 (✓) - 一键将 AI 提取的记忆置信度提升至 100%
- 安全删除 (✗) - 需二次确认的删除操作
- 详情弹窗 - 完整信息 + JSON 原始数据 + 内容编辑

### 批量操作 (New)
- 多选模式 - 批量选择记忆
- 批量验证 - 一键验证多条记忆
- 批量删除 - 确认后批量删除

### 时间线分析 (New)
- 堆叠面积图展示记忆分布
- 时间范围筛选 (7天/30天/90天/全部)
- 粒度切换 (按天/周/月)
- 层级分布统计

### 多项目支持 (New)
- 项目选择器 - 下拉切换项目
- 显示项目类型和宪法层状态
- 环境变量提示切换

### 多语言支持 (New)
- 中文 (默认)
- English
- 自动检测浏览器语言
- 一键切换，LocalStorage 持久化

## 组件结构

```
src/
├── components/
│   ├── Header.tsx           # 顶部导航
│   ├── SearchBar.tsx        # 搜索框
│   ├── FilterPanel.tsx      # 左侧筛选面板
│   ├── MemoryCard.tsx       # 记忆卡片
│   ├── MemoryList.tsx       # 记忆列表
│   ├── MemoryDetail.tsx     # 详情弹窗
│   ├── JsonViewer.tsx       # JSON 查看器
│   ├── ConfirmDialog.tsx    # 确认弹窗
│   ├── ProjectSelector.tsx  # 项目选择器
│   ├── LanguageSwitcher.tsx # 语言切换器
│   └── timeline/
│       ├── TimelineChart.tsx   # 时间线图表
│       └── TimelineFilters.tsx # 时间筛选器
├── pages/
│   └── TimelinePage.tsx     # 时间线页面
├── hooks/
│   ├── useMemories.ts       # 记忆数据 Hook
│   ├── useMemoryActions.ts  # 操作 Hook (验证/删除/更新)
│   ├── useSelection.ts      # 多选 Hook
│   ├── useProject.ts        # 项目管理 Hook
│   └── useTimelineData.ts   # 时间线数据 Hook
├── api/
│   └── memory.ts            # API 客户端
├── i18n/
│   ├── index.ts             # i18n 配置
│   └── locales/
│       ├── zh.json          # 中文翻译
│       └── en.json          # 英文翻译
├── types.ts                 # TypeScript 类型定义
└── App.tsx                  # 主应用
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
- `PATCH /api/v1/notes/{id}` - 更新记忆
- `DELETE /api/v1/notes/{id}` - 删除记忆
- `POST /api/v1/notes/{id}/verify` - 验证记忆
- `GET /api/v1/projects` - 获取项目列表
- `GET /api/v1/projects/current` - 获取当前项目

## 环境变量

在 `.env.local` 中配置：

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 更新日志

### 2025-12-28
- 添加批量操作功能（多选、批量验证、批量删除）
- 添加多项目切换支持
- 添加 i18n 国际化（中文/英文）
- 添加时间线分析页面（时间范围筛选、粒度切换）
