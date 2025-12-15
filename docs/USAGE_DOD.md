# DoD（Definition of Done）- 使用侧“可用”标准

目标：让技术小白每天用起来，不在链路里崩溃。

## Day-0（第一次装好）

- 你能在仓库根目录运行 `./ma doctor --project <name>` 并看到 **全部 OK**。
- `~/.memory-anchor/projects/<name>/constitution.yaml` 存在，且至少 1 条有效条目（不含真实隐私/密钥）。
- Claude（MCP）或 Codex（SDK）至少一种路径能正常 `search_memory/get_constitution`。

## Day-1（每天稳定使用）

- 你只需要记住 3 个命令：`./ma init`（一次）、`./ma up`（每天）、`./ma doctor`（出问题时）。
- 发生红叉/端口冲突时，`./ma doctor` 能给出 **可直接复制执行** 的修复建议。
- 不需要人为处理端口：默认使用 MCP stdio（不开端口）；只有显式用 HTTP 才检查端口。

## Escapes（高级但不影响傻瓜路径）

- 需要多客户端并发/共享：启动 Qdrant Server 并设置 `QDRANT_URL=http://localhost:6333`。
- 需要 HTTP API：用 `memory-anchor serve --mode http --port 8000`，先 `./ma doctor --http` 确认端口不冲突。

