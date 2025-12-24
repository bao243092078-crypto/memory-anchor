# Checklist（清单革命）功能实现说明

## 已完成的文件

### 1. 类型定义
- **文件**: `src/types/checklist.ts`
- **内容**:
  - `ChecklistStatus`: 清单状态（open, done, cancelled）
  - `ChecklistScope`: 作用域（project, session, global）
  - `ChecklistPriority`: 优先级（1-5）
  - `ChecklistItem`: 清单项接口
  - `PRIORITY_CONFIG`: 优先级配置（图标、颜色）
  - `STATUS_CONFIG`: 状态配置
  - `SCOPE_CONFIG`: 作用域配置

### 2. API 客户端
- **文件**: `src/api/checklist.ts`
- **功能**:
  - `getChecklistBriefing()`: 获取清单简报
  - `getChecklistItems()`: 获取清单列表
  - `createChecklistItem()`: 创建清单项
  - `updateChecklistItem()`: 更新清单项
  - `deleteChecklistItem()`: 删除清单项
  - `syncFromPlan()`: 从 Plan 同步

### 3. React Hooks
- **文件**: `src/hooks/useChecklist.ts`
- **Hooks**:
  - `useChecklistBriefing()`: 获取简报数据
  - `useChecklistItems()`: 获取清单列表
  - `useCreateChecklistItem()`: 创建 mutation
  - `useUpdateChecklistItem()`: 更新 mutation
  - `useDeleteChecklistItem()`: 删除 mutation
  - `useSyncFromPlan()`: 同步 mutation

### 4. UI 组件
- **文件**: `src/components/Checklist/ChecklistItem.tsx`
  - 清单项卡片组件
  - 支持复选框切换完成状态
  - 显示优先级、状态、作用域
  - 支持编辑和删除操作
  - 显示 `(ma:xxxxxxxx)` 引用 ID
  
- **文件**: `src/components/Checklist/ChecklistForm.tsx`
  - 清单项表单组件
  - 支持创建和编辑模式
  - 包含内容、优先级、作用域、标签、截止日期字段

### 5. 页面组件
- **文件**: `src/pages/Checklist.tsx`
  - 完整的清单管理页面
  - 显示 Markdown 格式的清单简报
  - 按优先级分组显示清单项（🔴紧急/🟠高优/🟡普通/🟢低优/⚪待定）
  - 支持按作用域和优先级筛选
  - 支持创建、编辑、删除、标记完成

### 6. 路由配置
- **文件**: `src/App.tsx`
  - 添加 `/checklist` 路由

### 7. 侧边栏菜单
- **文件**: `src/components/Layout/Sidebar.tsx`
  - 添加"清单"菜单项（CheckSquare 图标）

## 功能特性

### 优先级系统
- 🔴 **紧急** (Priority 1): 红色标识
- 🟠 **高优** (Priority 2): 橙色标识
- 🟡 **普通** (Priority 3): 黄色标识，默认值
- 🟢 **低优** (Priority 4): 绿色标识
- ⚪ **待定** (Priority 5): 灰色标识

### 状态管理
- ⏳ **待处理** (open): 默认状态
- ✅ **已完成** (done): 可点击复选框切换
- ❌ **已取消** (cancelled): 灰色显示，不可操作

### 作用域
- **项目级** (project): 仅限当前项目
- **会话级** (session): 当前会话临时任务
- **全局** (global): 跨项目通用任务

### 界面功能
1. **清单简报**: Markdown 格式显示，自动从后端获取
2. **按优先级分组**: 5 个优先级分别显示
3. **筛选功能**: 支持按作用域和优先级筛选
4. **快速操作**: 点击复选框快速标记完成
5. **详细编辑**: 编辑内容、优先级、标签、截止日期
6. **Memory Anchor 引用**: 自动提取并显示 `(ma:xxxxxxxx)` ID

## 后端 API 要求

需要实现以下端点：

```
GET  /api/v1/checklist/briefing?project_id=xxx&scope=project&limit=12
GET  /api/v1/checklist/items?project_id=xxx&scope=project&priority=1
POST /api/v1/checklist/items
     body: { project_id, content, scope, priority, tags }
PUT  /api/v1/checklist/items/{id}
     body: { status, content, priority, tags }
DELETE /api/v1/checklist/items/{id}
POST /api/v1/checklist/sync
     body: { project_id, plan_markdown, session_id }
```

## 使用说明

### 创建清单项
1. 点击"新建清单项"按钮
2. 填写内容、选择优先级、作用域
3. 可选填写标签和截止日期
4. 点击"创建"

### 标记完成
- 直接点击清单项左侧的复选框

### 编辑清单项
1. 点击清单项右上角的"..."菜单
2. 选择"编辑"
3. 修改内容后保存

### 删除清单项
1. 点击清单项右上角的"..."菜单
2. 选择"删除"
3. 确认删除

## 技术栈

- **React 18**: UI 框架
- **TanStack Query**: 数据获取和缓存
- **TypeScript**: 类型安全
- **Tailwind CSS**: 样式
- **lucide-react**: 图标
- **react-markdown**: Markdown 渲染
- **clsx**: 条件样式

## 代码质量

- ✅ TypeScript 类型安全
- ✅ 响应式设计（移动端友好）
- ✅ 统一的设计语言（与 Notes、Dashboard 一致）
- ✅ 数据自动刷新（mutation 后自动 invalidate queries）
- ✅ 加载状态和错误处理
- ✅ 空状态提示

## 下一步

后端需要实现：
1. `backend/api/checklist.py`: API 路由
2. `backend/services/checklist.py`: 业务逻辑
3. `backend/models/checklist.py`: 数据模型
4. 数据库表：`checklist_items`
