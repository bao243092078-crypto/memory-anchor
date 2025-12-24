# SOP: Qdrant Server 启动

**触发条件**：
- 会话开始时 Qdrant 未运行
- MCP 报 `QDRANT_URL must be set` 错误
- 出现 502 Bad Gateway

**前置条件**：
- Qdrant 二进制已安装 (`~/bin/qdrant`)
- 配置文件存在 (`~/.qdrant_storage/config/config.yaml`)

**预期结果**：
- Qdrant Server 在 6333 端口监听
- MCP 可正常连接

---

## 步骤

### 1. 检查是否已运行

```bash
curl -s http://127.0.0.1:6333/collections | head -c 100
```

如果返回 JSON，说明已运行，跳到步骤 4。

### 2. 检查代理干扰

如果 curl 返回 502 或超时：

```bash
# 检查是否有代理
echo $ALL_PROXY $HTTP_PROXY $HTTPS_PROXY

# 绕过代理测试
NO_PROXY=localhost,127.0.0.1 curl -s http://127.0.0.1:6333/collections
```

### 3. 启动 Qdrant Server

```bash
cd ~/.qdrant_storage && ~/bin/qdrant --config-path ./config/config.yaml &
```

等待 5 秒后验证。

### 4. 验证连接

```bash
curl -s http://127.0.0.1:6333/collections | jq '.collections[].name'
```

预期输出包含 `memory_anchor_notes` 或类似 collection。

---

## 常见问题

### Q: 返回 502 Bad Gateway
A: 通常是代理干扰。使用 `NO_PROXY=localhost,127.0.0.1` 前缀。

### Q: MCP 仍然连不上
A: MCP 可能在 Qdrant 启动前已启动。需要重启 Claude Code。

### Q: 端口被占用
A: 检查 `lsof -i :6333`，kill 旧进程后重试。

---

## 相关文件
- `.ai/operations/sop-memory-sync.md` - 记忆同步 SOP
- `~/.claude/rules-lite/13-memory-sync.md` - 全局记忆同步规则
