# SOP: 测试质量保护（Test Integrity Protection）

**触发条件**：
- AI 尝试修改 `**/test_*.py`、`**/*_test.py`、`**/*.test.ts` 等测试文件
- 测试失败后 AI 提议修改测试而非代码
- 用户说"检查测试质量"、"审查测试修改"

**前置条件**：
- 已了解测试失败的根本原因
- 已阅读相关源代码

**预期结果**：
- 测试完整性得到保护
- 可疑修改被拦截或警告
- 修复代码而非修改测试

---

## 核心原则

> **修复代码，而非修改测试来"通过"**

测试是质量的守护者。当测试失败时，问题通常在被测代码，而非测试本身。

---

## 禁止的测试修改（红线）

| 模式 | 说明 | 检测规则 |
|------|------|---------|
| 删除 `assert` | 削弱测试覆盖 | `old_string` 含 `assert`，`new_string` 不含 |
| 无理由 `@skip` | 跳过失败测试 | 添加 `@pytest.mark.skip` 且无 `reason=` |
| 修改期望值 | 掩盖 Bug | `assert x == Y` 中 Y 被修改 |
| 吞掉异常 | 隐藏错误 | 添加 `except: pass` 或 `except Exception: pass` |
| 删除边界测试 | 忽略边缘情况 | 删除含 `boundary`、`edge`、`limit` 的测试 |

---

## 允许的测试修改

| 行为 | 条件 |
|------|------|
| 添加新测试 | 增加覆盖率 ✅ |
| 修复测试 Bug | 测试本身有逻辑错误（需说明） |
| 更新期望值 | **接口变更时**，需在 commit message 说明 |
| 添加 `@skip` | **必须**有 `reason="TODO: ..."` 说明修复计划 |
| 重构测试 | 不改变断言逻辑 |

---

## 检测流程

### 1. PreToolUse Hook 自动检测

当 AI 调用 `Edit` 或 `Write` 修改测试文件时：

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检测是否修改测试文件                                │
│     file_path matches **/test_*.py | **/*_test.py | etc.   │
│     ↓                                                        │
│  Step 2: 分析修改内容                                        │
│     检查 old_string → new_string 的差异                      │
│     ↓                                                        │
│  Step 3: 模式匹配                                            │
│     匹配禁止模式 → 触发警告/阻止                              │
│     ↓                                                        │
│  Step 4: 返回决定                                            │
│     BLOCK（严重）/ REQUIRE_CONFIRM（警告）/ ALLOW（安全）    │
└─────────────────────────────────────────────────────────────┘
```

### 2. 检测模式示例

```python
# 🔴 危险：删除 assert
old: "    assert result == expected"
new: ""  # 或注释掉

# 🔴 危险：无理由 skip
old: "def test_critical():"
new: "@pytest.mark.skip\ndef test_critical():"

# 🟡 警告：修改期望值（需确认）
old: "assert calculate(10) == 100"
new: "assert calculate(10) == 99"

# 🔴 危险：吞掉异常
old: "result = risky_operation()"
new: "try:\n    result = risky_operation()\nexcept:\n    pass"
```

### 3. 处理流程

| 检测结果 | 行动 | 说明 |
|---------|------|------|
| **BLOCK** | 阻止执行 | 严重违规，必须修复代码 |
| **REQUIRE_CONFIRM** | 请求确认 | 可疑修改，需用户说明理由 |
| **ALLOW** | 允许执行 | 安全修改（添加测试等） |

---

## 手动检查清单

当 Hook 未启用或需要人工审查时：

### Pre-Modification Checklist

- [ ] 测试失败的原因已分析
- [ ] 问题在**源代码**还是**测试代码**？
- [ ] 如果要改测试，有合理理由吗？

### Post-Modification Checklist

- [ ] 没有删除任何 `assert`
- [ ] 没有添加无理由的 `@skip`
- [ ] 期望值修改有说明
- [ ] 测试逻辑没有被弱化

---

## 常见问题

### Q: 测试失败了，我能修改测试吗？

A: **先问自己**：
1. 测试本身有 Bug 吗？（罕见）→ 修复测试，说明原因
2. 接口/需求变更了吗？→ 更新测试，记录变更
3. 代码有 Bug 吗？（最常见）→ **修复代码**，不动测试

### Q: 如何添加合规的 skip？

A: 必须有 reason 参数：
```python
@pytest.mark.skip(reason="TODO: 需要 mock 外部 API，见 issue #123")
def test_external_api():
    ...
```

### Q: 期望值确实需要修改怎么办？

A: 在 commit message 中说明：
```
fix: update test expected value after API change

接口 `calculate()` 的返回值精度从 int 改为 float，
更新测试期望值以反映新行为。
```

---

## 相关文件

- `CLAUDE.md` - 测试完整性红线规则定义
- `backend/hooks/test_tampering_hook.py` - PreToolUse Hook 实现
- `.ai/test-mapping.yaml` - 测试映射规则
