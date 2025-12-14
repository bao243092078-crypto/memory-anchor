#!/usr/bin/env python3
"""
Memory Harvester - 从现有项目的 CLAUDE.md 和 CURRENT_TASK.md 中收割记忆

用法：
    # 收割所有项目
    python scripts/harvest_memories.py --all

    # 收割指定项目
    python scripts/harvest_memories.py --project ~/projects/跨境2

    # 干运行（不写入）
    python scripts/harvest_memories.py --all --dry-run

    # 显示详细信息
    python scripts/harvest_memories.py --all --verbose
"""

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid5

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")

from backend.services.search import SearchService

# 用于生成幂等 ID 的命名空间
NAMESPACE_MEMORY_ANCHOR = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# 项目根目录
PROJECTS_ROOT = Path.home() / "projects"

# 要扫描的文件模式
MEMORY_FILES = [
    "CLAUDE.md",
    ".claude/CURRENT_TASK.md",
    "CURRENT_TASK.md",
    ".claude/state/progress_*.md",
]

# 要排除的目录
EXCLUDE_DIRS = [
    "node_modules",
    ".venv",
    "__pycache__",
    ".git",
    ".qdrant",
    ".memos",
]


def generate_note_id(project_id: str, content: str) -> UUID:
    """
    生成幂等的 note ID。

    基于项目 ID 和内容哈希生成，确保相同内容不会重复。
    """
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    return uuid5(NAMESPACE_MEMORY_ANCHOR, f"{project_id}:{content_hash}")


def extract_project_id(path: Path) -> str:
    """
    从路径提取项目 ID。

    例如：/Users/baobao/projects/跨境2/CLAUDE.md -> kuajing2
    """
    # 找到 projects 目录下的第一级目录
    parts = path.parts
    try:
        projects_idx = parts.index("projects")
        project_name = parts[projects_idx + 1]
        # 安全过滤：只保留字母数字和下划线
        safe_name = "".join(c for c in project_name if c.isalnum() or c in ("_", "-"))
        return safe_name or "default"
    except (ValueError, IndexError):
        return "default"


def parse_memory_anchor_blocks(content: str) -> list[dict]:
    """
    解析 ```memory-anchor``` 代码块。

    返回结构化的记忆列表。
    """
    import yaml

    pattern = r"```memory-anchor\n(.*?)```"
    blocks = re.findall(pattern, content, re.DOTALL)

    memories = []
    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if data and isinstance(data, dict):
                memories.append({
                    "id": data.get("id"),
                    "type": data.get("type", "note"),
                    "summary": data.get("summary", ""),
                    "details": data.get("details"),
                    "layer": data.get("layer", "fact"),
                    "tags": data.get("tags", []),
                    "source": "memory-anchor-block",
                })
        except Exception:
            continue

    return memories


def extract_decisions_from_markdown(content: str, source_file: str) -> list[dict]:
    """
    从 Markdown 内容中提取决策、Bug 修复等记忆。

    使用启发式规则识别重要内容。
    """
    memories = []

    # 1. 解析 memory-anchor 代码块（优先）
    memories.extend(parse_memory_anchor_blocks(content))

    # 2. 提取项目概述（第一个 # 标题）
    title_match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
    if title_match:
        project_title = title_match.group(1).strip()
        # 获取标题后的第一段描述
        desc_match = re.search(r"^#\s+.+?\n\n(.+?)(?=\n\n|\n#|\Z)", content, re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip()
            # 清理 Markdown 格式
            desc = re.sub(r"\*\*(.+?)\*\*", r"\1", desc)  # 移除加粗
            desc = re.sub(r"`(.+?)`", r"\1", desc)  # 移除代码标记
            if len(desc) > 20:
                memories.append({
                    "type": "decision",
                    "summary": f"项目: {project_title} - {desc[:150]}",
                    "layer": "fact",
                    "source": f"overview:{source_file}",
                })

    # 3. 提取架构信息（## Architecture 或 ## 架构）
    arch_patterns = [
        r"##\s*(?:Architecture|架构|4 Agent 架构|Domain Architecture)[^\n]*\n(.*?)(?=\n##|\Z)",
        r"##\s*(?:核心业务链路|Business Flow)[^\n]*\n(.*?)(?=\n##|\Z)",
    ]
    for pattern in arch_patterns:
        arch_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if arch_match:
            arch_content = arch_match.group(1).strip()
            # 提取代码块中的架构图
            code_match = re.search(r"```[^\n]*\n(.*?)```", arch_content, re.DOTALL)
            if code_match:
                arch_diagram = code_match.group(1).strip()
                if len(arch_diagram) > 20:
                    memories.append({
                        "type": "decision",
                        "summary": f"架构: {arch_diagram[:200]}",
                        "layer": "fact",
                        "source": f"architecture:{source_file}",
                    })
                    break

    # 4. 提取服务端口信息
    port_match = re.search(r"##\s*(?:Service Ports|端口|Ports)[^\n]*\n(.*?)(?=\n##|\Z)",
                           content, re.DOTALL | re.IGNORECASE)
    if port_match:
        ports_content = port_match.group(1).strip()
        # 提取表格中的端口信息
        port_lines = []
        for line in ports_content.split("\n"):
            if re.search(r"\|\s*\d+\s*\|", line):
                port_lines.append(line.strip())
        if port_lines:
            memories.append({
                "type": "note",
                "summary": f"服务端口: {'; '.join(port_lines[:3])}",
                "layer": "fact",
                "source": f"ports:{source_file}",
            })

    # 5. 提取启动命令
    cmd_patterns = [
        r"##\s*(?:Development Commands|启动|Commands|Quick Start)[^\n]*\n(.*?)(?=\n##|\Z)",
        r"##\s*(?:One-Click Start|快速启动)[^\n]*\n(.*?)(?=\n##|\Z)",
    ]
    for pattern in cmd_patterns:
        cmd_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if cmd_match:
            cmd_content = cmd_match.group(1).strip()
            # 提取第一个代码块
            code_match = re.search(r"```(?:bash|sh)?\n(.*?)```", cmd_content, re.DOTALL)
            if code_match:
                commands = code_match.group(1).strip()
                if len(commands) > 10:
                    memories.append({
                        "type": "note",
                        "summary": f"启动命令: {commands[:150]}",
                        "layer": "fact",
                        "source": f"commands:{source_file}",
                    })
                    break

    # 6. 提取曾国藩心法（如果有）
    doctrine_match = re.search(r"##\s*曾国藩心法[^\n]*\n(.*?)(?=\n##|\Z)",
                               content, re.DOTALL)
    if doctrine_match:
        doctrine = doctrine_match.group(1).strip()
        # 提取六字诀
        six_match = re.search(r"\*\*六字诀\*\*[：:]\s*(.+?)(?=\n|\Z)", doctrine)
        if six_match:
            memories.append({
                "type": "decision",
                "summary": f"开发准则: {six_match.group(1)[:150]}",
                "layer": "fact",
                "source": f"doctrine:{source_file}",
            })

    # 7. 提取关键文件列表
    files_match = re.search(r"##\s*(?:关键文件|Key Files|Important Files)[^\n]*\n(.*?)(?=\n##|\Z)",
                            content, re.DOTALL | re.IGNORECASE)
    if files_match:
        files_content = files_match.group(1).strip()
        # 提取列表项
        file_items = re.findall(r"[-*]\s*`([^`]+)`\s*[-–]\s*(.+?)(?=\n|$)", files_content)
        if file_items:
            files_summary = "; ".join([f"{f}: {d[:30]}" for f, d in file_items[:5]])
            memories.append({
                "type": "note",
                "summary": f"关键文件: {files_summary[:200]}",
                "layer": "fact",
                "source": f"files:{source_file}",
            })

    # 8. 提取待配置/环境变量
    env_match = re.search(r"##\s*(?:待配置|Environment|Configuration)[^\n]*\n(.*?)(?=\n##|\Z)",
                          content, re.DOTALL | re.IGNORECASE)
    if env_match:
        env_content = env_match.group(1).strip()
        # 提取 export 语句
        exports = re.findall(r"export\s+(\w+)=", env_content)
        if exports:
            memories.append({
                "type": "note",
                "summary": f"需要配置: {', '.join(exports[:5])}",
                "layer": "session",
                "source": f"env:{source_file}",
            })

    # 9. 提取 CURRENT_TASK.md 的任务状态
    if "CURRENT_TASK" in source_file or "progress_" in source_file:
        # 提取整个文件内容作为任务状态
        first_lines = "\n".join(content.strip().split("\n")[:10])
        if len(first_lines) > 20:
            memories.append({
                "type": "note",
                "summary": f"当前任务: {first_lines[:200]}",
                "layer": "session",
                "source": f"task:{source_file}",
            })

    return memories


def discover_memory_files(root: Path) -> list[Path]:
    """
    发现所有需要扫描的记忆文件。
    """
    files = []

    for pattern in MEMORY_FILES:
        if "*" in pattern:
            # glob 模式
            files.extend(root.glob(pattern))
        else:
            # 直接文件
            file_path = root / pattern
            if file_path.exists():
                files.append(file_path)

    return files


def discover_projects() -> list[Path]:
    """
    发现所有项目目录。
    """
    projects = []

    if not PROJECTS_ROOT.exists():
        print(f"警告: 项目根目录不存在: {PROJECTS_ROOT}")
        return projects

    for item in PROJECTS_ROOT.iterdir():
        if item.is_dir() and item.name not in EXCLUDE_DIRS:
            # 检查是否有 CLAUDE.md 或其他记忆文件
            has_memory_file = any(
                (item / pattern.split("*")[0]).exists() or list(item.glob(pattern))
                for pattern in MEMORY_FILES
            )
            if has_memory_file:
                projects.append(item)

    return projects


def harvest_project(
    project_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[int, int]:
    """
    收割单个项目的记忆。

    Returns:
        (发现的记忆数, 写入的记忆数)
    """
    project_id = extract_project_id(project_path)
    memory_files = discover_memory_files(project_path)

    if verbose:
        print(f"\n📂 项目: {project_path.name} (ID: {project_id})")
        print(f"   找到 {len(memory_files)} 个记忆文件")

    all_memories = []

    for file_path in memory_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            relative_path = str(file_path.relative_to(project_path))
            memories = extract_decisions_from_markdown(content, relative_path)

            for memory in memories:
                memory["project_id"] = project_id
                memory["file_path"] = relative_path

            all_memories.extend(memories)

            if verbose and memories:
                print(f"   📄 {relative_path}: {len(memories)} 条记忆")
        except Exception as e:
            if verbose:
                print(f"   ⚠️ 读取失败 {file_path}: {e}")

    if dry_run:
        if verbose:
            for m in all_memories:
                print(f"      [{m['type']}] {m['summary'][:80]}...")
        return len(all_memories), 0

    # 写入 Qdrant
    if not all_memories:
        return 0, 0

    try:
        # 为每个项目创建独立的 SearchService
        os.environ["MCP_MEMORY_PROJECT_ID"] = project_id
        from backend.config import reset_config
        reset_config()  # 重置配置以使用新的项目 ID

        service = SearchService()

        notes_to_index = []
        for memory in all_memories:
            note_id = generate_note_id(project_id, memory["summary"])
            notes_to_index.append({
                "id": note_id,
                "content": memory["summary"],
                "layer": memory.get("layer", "fact"),
                "category": "event",  # 默认类别
                "is_active": True,
                "confidence": 0.85,  # 从文件提取的默认置信度
                "source": memory.get("source", f"harvest:{project_id}"),
                "created_at": datetime.now().isoformat(),
            })

        indexed_count = service.index_notes_batch(notes_to_index)

        if verbose:
            print(f"   ✅ 写入 {indexed_count} 条记忆到 collection: {service.collection_name}")

        return len(all_memories), indexed_count

    except Exception as e:
        print(f"   ❌ 写入失败: {e}")
        return len(all_memories), 0


def main():
    parser = argparse.ArgumentParser(
        description="从项目的 CLAUDE.md 和 CURRENT_TASK.md 中收割记忆"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="收割所有项目",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="收割指定项目",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干运行，不实际写入",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息",
    )

    args = parser.parse_args()

    if not args.all and not args.project:
        parser.print_help()
        sys.exit(1)

    print("🌾 Memory Harvester 启动")
    print(f"   Qdrant URL: {os.environ.get('QDRANT_URL', 'Not set')}")

    if args.dry_run:
        print("   模式: 干运行（不写入）")

    total_found = 0
    total_indexed = 0

    if args.all:
        projects = discover_projects()
        print(f"\n发现 {len(projects)} 个项目")

        for project in projects:
            found, indexed = harvest_project(
                project,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            total_found += found
            total_indexed += indexed
    else:
        project_path = args.project.expanduser().resolve()
        if not project_path.exists():
            print(f"❌ 项目不存在: {project_path}")
            sys.exit(1)

        found, indexed = harvest_project(
            project_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        total_found += found
        total_indexed += indexed

    print(f"\n📊 收割完成")
    print(f"   发现记忆: {total_found}")
    print(f"   写入记忆: {total_indexed}")


if __name__ == "__main__":
    main()
