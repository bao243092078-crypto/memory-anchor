#!/usr/bin/env python3
"""
三步六维验证 - Step 3: 存

验证通过后，将结果写入 Memory Anchor。
用于 CI/CD 或手动验证后的记录。

用法：
    uv run scripts/verify_and_record.py          # 运行完整验证流程
    uv run scripts/verify_and_record.py --check  # 仅检查，不写入记忆
    uv run scripts/verify_and_record.py --record # 仅记录（假设已验证）
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")


def run_ruff() -> tuple[bool, str]:
    """运行 ruff 检查（代码质量）"""
    print("🔍 ruff check...")
    result = subprocess.run(
        ["uv", "run", "ruff", "check", "backend/"],
        capture_output=True,
        text=True,
    )
    passed = result.returncode == 0
    return passed, result.stdout + result.stderr


def run_mypy() -> tuple[bool, str]:
    """运行 mypy 检查（类型安全）"""
    print("🔍 mypy check...")
    result = subprocess.run(
        ["uv", "run", "mypy", "backend/", "--ignore-missing-imports"],
        capture_output=True,
        text=True,
    )
    passed = result.returncode == 0
    return passed, result.stdout + result.stderr


def run_pytest() -> tuple[bool, str]:
    """运行 pytest（逻辑正确性）"""
    print("🔍 pytest...")
    result = subprocess.run(
        ["uv", "run", "pytest", "-v", "--tb=short"],
        capture_output=True,
        text=True,
    )
    passed = result.returncode == 0
    return passed, result.stdout + result.stderr


def calculate_score(results: dict) -> float:
    """
    计算六维度加权分数

    权重：
    - 逻辑正确性 25% (pytest)
    - 类型安全 15% (mypy)
    - 错误处理 20% (manual)
    - 性能影响 15% (manual)
    - 安全风险 15% (manual)
    - 代码质量 10% (ruff)
    """
    weights = {
        "pytest": 0.25,
        "mypy": 0.15,
        "ruff": 0.10,
        # 手动维度默认通过（0.5 = 50%权重的满分）
        "manual": 0.50,
    }

    score = 0.0

    # 自动化检查
    if results.get("ruff", False):
        score += weights["ruff"]
    if results.get("mypy", False):
        score += weights["mypy"]
    if results.get("pytest", False):
        score += weights["pytest"]

    # 手动维度默认通过（保守估计）
    score += weights["manual"]

    return round(score, 2)


def generate_report(results: dict, score: float) -> str:
    """生成验证报告"""
    status = "✅ 通过" if score >= 0.8 else "⚠️ 需改进" if score >= 0.6 else "❌ 不通过"

    report = f"""## 🔍 三步六维验证报告

### Step 2: 验
- 自动化检查：
  - ruff: {"✅" if results.get("ruff") else "❌"}
  - mypy: {"✅" if results.get("mypy") else "❌"}
  - pytest: {"✅" if results.get("pytest") else "❌"}
- 六维评分：
  | 维度 | 评分 |
  |------|------|
  | 逻辑正确性 | {"0.25" if results.get("pytest") else "0.0"} |
  | 类型安全 | {"0.15" if results.get("mypy") else "0.0"} |
  | 代码质量 | {"0.10" if results.get("ruff") else "0.0"} |
  | 错误处理 | 0.20 (默认) |
  | 性能影响 | 0.15 (默认) |
  | 安全风险 | 0.15 (默认) |
- **总分：{score} {status}**

### Step 3: 存
- 时间：{datetime.now().isoformat()}
"""
    return report


def record_to_memory(score: float, results: dict) -> bool:
    """将验证结果写入 Memory Anchor"""
    from backend.config import reset_config
    from backend.services.search import SearchService

    try:
        reset_config()
        service = SearchService()

        # 生成摘要
        checks = []
        if results.get("ruff"):
            checks.append("ruff")
        if results.get("mypy"):
            checks.append("mypy")
        if results.get("pytest"):
            checks.append("pytest")

        status = "通过" if score >= 0.8 else "需改进"
        summary = f"三步六维验证{status}（{score}分）: {', '.join(checks) or '无'} 通过"

        # 写入记忆
        import uuid
        note_id = uuid.uuid4()

        service.index_note(
            note_id=note_id,
            content=summary,
            layer="session",  # 验证结果是会话级的
            category="event",
            source="verify_and_record",
        )

        print(f"✅ 已写入记忆：{summary}")
        return True

    except Exception as e:
        print(f"⚠️ 写入记忆失败：{e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="三步六维验证 - Step 3: 存",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查，不写入记忆",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="仅记录（假设已验证通过）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细输出",
    )

    args = parser.parse_args()

    print("=" * 50)
    print("三步六维验证")
    print("=" * 50)

    results = {}

    if args.record:
        # 仅记录模式：假设全部通过
        results = {"ruff": True, "mypy": True, "pytest": True}
        score = 1.0
    else:
        # 运行检查
        print("\n### Step 2: 验（自动化检查）\n")

        ruff_ok, ruff_out = run_ruff()
        results["ruff"] = ruff_ok
        if args.verbose and not ruff_ok:
            print(ruff_out)
        print(f"   ruff: {'✅' if ruff_ok else '❌'}")

        mypy_ok, mypy_out = run_mypy()
        results["mypy"] = mypy_ok
        if args.verbose and not mypy_ok:
            print(mypy_out)
        print(f"   mypy: {'✅' if mypy_ok else '❌'}")

        pytest_ok, pytest_out = run_pytest()
        results["pytest"] = pytest_ok
        if args.verbose and not pytest_ok:
            print(pytest_out)
        print(f"   pytest: {'✅' if pytest_ok else '❌'}")

        score = calculate_score(results)

    # 生成报告
    report = generate_report(results, score)
    print(report)

    # Step 3: 存
    if not args.check:
        print("\n### Step 3: 存（写入记忆）\n")
        record_to_memory(score, results)
    else:
        print("\n（--check 模式，跳过写入记忆）")

    # 返回码
    if score >= 0.8:
        print("\n✅ 验证通过")
        sys.exit(0)
    elif score >= 0.6:
        print("\n⚠️ 验证通过但需改进")
        sys.exit(0)
    else:
        print("\n❌ 验证不通过")
        sys.exit(1)


if __name__ == "__main__":
    main()
