# Memory Anchor 多项目隔离 - 快速参考

> **更新时间**: 2025-12-18
> **配置状态**: ✅ 32 个项目已初始化

---

## 📋 5 秒检查清单

```bash
# 1. 检查 Qdrant Server
ps aux | grep qdrant | grep -v grep  # 应该有进程运行

# 2. 检查当前项目配置
ls -la .memory-anchor/config.yaml    # 应该存在

# 3. 检查隔离状态
/Users/baobao/projects/阿默斯海默症/scripts/check_memory_isolation.sh

# 4. 验证记忆不泄漏
# 在项目 A 写入 → 在项目 B 搜索 → 应该搜索不到
```

---

## 🎯 当前配置概览

### 已初始化项目（32个）

**配置文件**: `.memory-anchor/config.yaml`
**隔离模式**: `strict_mode: true`（默认）
**全局共享**: `share_global: false`（默认）

### 项目分类

| 类型 | 数量 | 项目 |
|------|------|------|
| **AI 开发** | 9 | ai编剧导演, ai服装公司, ai黑客, ai平面大师, ai手机大师, ai文案大师, ai营销大师, ai仲裁, 新ai销售 |
| **电商** | 2 | sextool, 跨境 2 |
| **基础设施** | 2 | apikey-manager, claude-flow |
| **通用** | 19 | 其他项目 |

### Qdrant Collections（35个）

**活跃**（11个，有记忆）:
- ai手机大师(12), global(12), 跨境2(6), ai服装公司(4), 阿默斯海默症(3), ai文案大师(2), ai平面大师(2), mcp-memory-service(2), claude-flow(1), 单独个人行为提升(1), sextool(1)

**空闲**（24个）:
- 可清理或保留

---

## 🔧 常用命令

### 检查隔离

```bash
# 在任意项目目录
cd /Users/baobao/projects/<项目名>
/Users/baobao/projects/阿默斯海默症/scripts/check_memory_isolation.sh
```

### 测试隔离（重要！）

```bash
# 1. 在项目 A 写入测试记忆
cd /Users/baobao/projects/ai手机大师
# 在 Claude Code 中执行：
# mcp__memory-anchor__add_memory(content="测试隔离-项目A专属", layer="session")

# 2. 在项目 B 搜索
cd /Users/baobao/projects/跨境2
# 在 Claude Code 中执行：
# mcp__memory-anchor__search_memory(query="测试隔离")
# 预期：搜索不到项目 A 的记忆 ✅
```

### 清理空 Collections

```bash
# 查看空 collections
curl -s http://localhost:6333/collections | jq -r '.result.collections[] | select(.points_count == 0) | .name'

# 删除指定 collection（谨慎！）
curl -X DELETE "http://localhost:6333/collections/COLLECTION_NAME"
```

### 查看项目记忆统计

```bash
# 所有项目的记忆数量
curl -s http://localhost:6333/collections | jq -r '.result.collections[] | "\(.name): \(.points_count) 条记忆"'
```

---

## 🚨 故障排查

### 问题 1: 搜索到其他项目的记忆

**症状**: 在项目 A 搜索时，返回了项目 B 的记忆

**检查**:
```bash
# 1. 检查项目配置
cat .memory-anchor/config.yaml | grep project_name

# 2. 检查 MCP 配置
cat .mcp.json | grep MCP_MEMORY_PROJECT_ID

# 3. 检查当前使用的 collection
curl -s 'http://localhost:8001/api/v1/search/stats'
```

**解决**:
- 确保 `.memory-anchor/config.yaml` 中 `project_name` 正确
- 确保 `.mcp.json` 中 `MCP_MEMORY_PROJECT_ID` 设置正确
- 重启 MCP 服务

### 问题 2: 配置文件不生效

**症状**: 修改了 `.memory-anchor/config.yaml` 但没有效果

**原因**: 配置加载优先级：
1. 环境变量（最高）
2. 项目配置 `.memory-anchor/config.yaml`
3. 全局配置 `~/.memory-anchor/config.yaml`
4. 默认值

**解决**:
- 检查是否有环境变量覆盖：`env | grep MEMORY_ANCHOR`
- 重启 MCP 服务加载新配置

### 问题 3: Qdrant Server 连接失败

**症状**: `QDRANT_URL must be set` 错误

**检查**:
```bash
# 1. 检查 Qdrant Server
ps aux | grep qdrant | grep -v grep

# 2. 测试连接
curl http://localhost:6333/collections
```

**解决**:
```bash
# 启动 Qdrant Server
cd ~/.qdrant_storage
~/bin/qdrant --config-path ./config/config.yaml &
```

---

## 📖 配置模板参考

### 严格隔离（默认，推荐）

```yaml
isolation:
  strict_mode: true
  share_global: false
```

**适用**: 所有项目（避免污染）

### 分层共享（高级）

```yaml
isolation:
  strict_mode: false
  share_collections:
    - "global"           # 全局通用知识
    - "ai-development"   # 或 "ecommerce", "infrastructure"
```

**适用**: 需要跨项目共享领域知识时

---

## 🔐 安全建议

### 1. 定期审计

```bash
# 每周检查一次隔离状态
/Users/baobao/projects/阿默斯海默症/scripts/check_memory_isolation.sh
```

### 2. 备份记忆

```bash
# 每月备份一次 Qdrant 数据
tar -czf ~/backups/qdrant_backup_$(date +%Y%m%d).tar.gz ~/.qdrant_storage/
```

### 3. 清理无用 Collections

```bash
# 删除 90 天未使用的空 collections
# （需要编写脚本，根据最后修改时间判断）
```

---

## 📞 快速支持

### 文档位置

- **完整配置指南**: `docs/PROJECT_MEMORY_TEMPLATE.md`
- **隔离检查脚本**: `scripts/check_memory_isolation.sh`
- **批量初始化脚本**: `scripts/init_all_projects.sh`

### 相关命令

```bash
# 查看帮助
cd /Users/baobao/projects/阿默斯海默症
uv run memory-anchor --help

# 查看 MCP Server 日志
tail -f /tmp/memory_anchor_server_8001.log
```

---

## ✅ 完成检查清单

初始化后确认：

- [ ] 所有项目有 `.memory-anchor/config.yaml`
- [ ] Qdrant 有 35 个 collections
- [ ] 每个 collection 独立命名
- [ ] 测试跨项目搜索（应该隔离）
- [ ] 备份配置文件到 git

---

**🎉 配置完成！现在你的 32 个项目都有独立的记忆系统了！**

最后更新: 2025-12-18 18:40
