# Day 7 检索质量测试报告

> **日期**: 2025-12-11
> **项目**: Memory Anchor（记忆锚点）
> **阶段**: Week 1 Day 7 - 检索测试

---

## 一、测试概览

| 项目 | 结果 |
|------|------|
| **总测试数** | 13 |
| **通过** | 13 ✅ |
| **失败** | 0 |
| **测试时间** | 3.57s |
| **Qdrant 模式** | Server (Docker) |
| **Embedding 模型** | paraphrase-multilingual-MiniLM-L12-v2 (384维) |

---

## 二、10个核心测试场景结果

### 检索质量测试 (TestRetrievalQuality)

| # | 测试场景 | 状态 | 说明 |
|---|---------|------|------|
| 1 | 宪法层始终返回 | ✅ PASSED | 无论查询内容，layer=constitution 过滤正常 |
| 2 | 同义词理解（闺女→女儿） | ✅ PASSED | "闺女电话是多少"能匹配"女儿王小红" |
| 3 | 语义理解（吃药时间→早餐后服用） | ✅ PASSED | "什么时候吃药"能匹配"早餐后服用阿司匹林" |
| 4 | 层级过滤（仅事实层） | ✅ PASSED | layer=fact 正确过滤 |
| 5 | 层级过滤（仅会话层） | ✅ PASSED | layer=session 正确过滤 |
| 6 | 类别过滤（仅人物） | ✅ PASSED | category=person 正确过滤 |
| 7 | 关键医疗信息（过敏） | ✅ PASSED | "过敏"能匹配"青霉素过敏" |
| 8 | 家庭关系（儿子信息） | ✅ PASSED | "儿子在哪里工作"能匹配"上海工作" |
| 9 | 过去事件（工作经历） | ✅ PASSED | "以前在哪里工作"能匹配"首钢工程师" |
| 10 | 今日安排 | ✅ PASSED | 会话层能返回今日安排信息 |

### 基础功能测试 (TestSearchServiceBasic)

| # | 测试场景 | 状态 | 说明 |
|---|---------|------|------|
| 11 | 连接模式 | ✅ PASSED | Server 模式正常连接 |
| 12 | Collection 存在 | ✅ PASSED | memory_anchor_notes 已创建 |
| 13 | 获取统计信息 | ✅ PASSED | get_stats() 正常返回 |

---

## 三、MCP Server 工具验证

### 3.1 add_memory 工具

| 测试 | 结果 |
|------|------|
| 添加 fact 层记忆 | ✅ 成功，返回 ID |
| 置信度 ≥ 0.9 自动保存 | ✅ 正常 |
| 返回格式 | ✅ 包含 status, layer, confidence, id |

### 3.2 search_memory 工具

| 查询 | 相关度 | 匹配内容 |
|------|--------|---------|
| "女儿电话" | 0.77 | 女儿王小红，电话13800138000 |
| "什么时候吃药" | 0.48 | 每天早餐后服用阿司匹林100mg |
| "过敏" | 0.73 | 对青霉素过敏，严禁使用 |

---

## 四、环境验证

### 4.1 Qdrant Server

```bash
# 启动命令
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v ~/.qdrant_storage:/qdrant/storage:z qdrant/qdrant

# 验证
curl http://localhost:6333/collections
# 返回: {"result":{"collections":[]},"status":"ok"}
```

### 4.2 memory.json 存储位置

**结论**: 不存在 NPX 临时目录问题

| 项目 | 值 |
|------|---|
| 存储路径 | `/Users/baobao/.mcp/memory.json` |
| 文件大小 | 142KB |
| 格式 | NDJSON (每行一个实体) |
| 最后修改 | 2025-12-11 12:26 |
| 持久化 | ✅ 稳定（~/.mcp/ 是固定目录）|

---

## 五、发现的问题与建议

### 5.1 已发现问题

1. **Embedding 模型 Warning**
   ```
   UserWarning: The model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 
   now uses mean pooling instead of CLS embedding.
   ```
   - 影响: 低（功能正常）
   - 建议: 可在后续版本固定 fastembed 版本

2. **语义相关度偏低**
   - "什么时候吃药" → "早餐后服用阿司匹林" 相关度仅 0.48
   - 建议: 考虑添加关键词混合检索提升召回

### 5.2 后续优化建议

| 优先级 | 建议 |
|--------|------|
| P1 | 添加关键词混合检索（BM25 + 向量） |
| P2 | 实现宪法层三次审批 API |
| P3 | 添加检索结果缓存 |
| P4 | 支持检索结果解释（为什么匹配） |

---

## 六、结论

**Day 7 检索测试通过** ✅

- 三层记忆模型的检索逻辑正常工作
- 层级/类别过滤正确
- 同义词和语义理解基本满足需求
- MCP Server 工具调用正常
- Qdrant Server 模式稳定运行

**下一步**: Week 1 Day 8-10 - 完善 MemoryService + 实现 /memory/add 和 /memory/search API
