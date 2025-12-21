#!/usr/bin/env python3
"""
Checkpoint Hook - 清单革命上下文保护机制

用于 Claude Code Hooks：
- PreCompact: 在上下文压缩前保存运行时状态
- SessionStart: 在会话开始时加载恢复清单

用法：
    uv run scripts/checkpoint.py save --project NAME       # PreCompact: 保存状态
    uv run scripts/checkpoint.py load --project NAME       # SessionStart: 加载清单
    uv run scripts/checkpoint.py status --project NAME     # 检查状态
    uv run scripts/checkpoint.py diff --project NAME       # 显示与上次保存的差异

设计原则（来自三方 AI 头脑风暴）：
- Plan skill = 战术层（单次任务）
- Memory Anchor = 战略层（跨会话持久）
- checkpoint.py = 桥梁（捕获运行时状态）
"""

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 确保使用 Qdrant Server 模式
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6333")


def detect_running_ports() -> list[dict]:
    """
    检测当前运行的开发端口

    常见开发端口：
    - 3000-3999: React/Next/Vite dev server
    - 5000-5999: Flask/FastAPI
    - 8000-8999: Django/FastAPI/general
    """
    ports = []
    dev_port_ranges = [(3000, 3999), (5000, 5999), (8000, 8999)]

    for port_start, port_end in dev_port_ranges:
        for port in range(port_start, port_end + 1, 100):  # 每100检查一个
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                if result == 0:
                    ports.append({"port": port, "status": "listening"})
            except Exception:
                pass

    # 也检查精确端口
    for port in [3000, 3001, 5000, 5173, 8000, 8080]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result == 0:
                if not any(p["port"] == port for p in ports):
                    ports.append({"port": port, "status": "listening"})
        except Exception:
            pass

    return ports


def detect_running_processes() -> list[dict]:
    """检测相关开发进程"""
    processes = []

    # 查找常见开发进程
    patterns = [
        ("node", "Node.js"),
        ("python", "Python"),
        ("uvicorn", "FastAPI"),
        ("vite", "Vite"),
        ("npm", "npm"),
    ]

    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.split("\n")

        for line in lines[1:]:  # 跳过 header
            for pattern, name in patterns:
                if pattern in line.lower():
                    parts = line.split()
                    if len(parts) >= 11:
                        processes.append(
                            {
                                "type": name,
                                "pid": parts[1],
                                "cmd": " ".join(parts[10:])[:100],  # 截断命令
                            }
                        )
                    break
    except Exception:
        pass

    return processes


def detect_qdrant_status() -> dict:
    """检测 Qdrant 服务状态"""
    qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")

    try:
        import urllib.request

        req = urllib.request.Request(f"{qdrant_url}/collections", method="GET")
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read())
            collections = data.get("result", {}).get("collections", [])
            return {
                "status": "online",
                "url": qdrant_url,
                "collections_count": len(collections),
            }
    except Exception as e:
        return {"status": "offline", "url": qdrant_url, "error": str(e)}


def detect_git_status() -> dict:
    """
    检测 git 仓库状态

    Returns:
        dict: 包含以下字段：
        - branch: 当前分支
        - uncommitted_changes: 未提交的文件列表 [{status, file}]
        - last_commit: 最后一次提交信息 {hash, message, author, date}
        - has_stash: 是否有 stash
        - ahead_behind: 与远程的差距 {ahead, behind}
    """
    result: dict[str, Any] = {
        "branch": None,
        "uncommitted_changes": [],
        "last_commit": None,
        "has_stash": False,
        "ahead_behind": {"ahead": 0, "behind": 0},
    }

    try:
        # 获取当前分支
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if branch_result.returncode == 0:
            result["branch"] = branch_result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # 获取未提交的变更（包括未跟踪文件）
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status_result.returncode == 0:
            lines = status_result.stdout.strip().split("\n")
            for line in lines:
                if line:
                    status_code = line[:2].strip()
                    file_path = line[3:]
                    result["uncommitted_changes"].append({
                        "status": status_code,
                        "file": file_path,
                    })
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # 获取最后一次提交信息
        log_result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%an|%ci"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if log_result.returncode == 0 and log_result.stdout.strip():
            parts = log_result.stdout.strip().split("|")
            if len(parts) >= 4:
                result["last_commit"] = {
                    "hash": parts[0][:8],
                    "message": parts[1][:100],  # 截断长消息
                    "author": parts[2],
                    "date": parts[3],
                }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # 检查是否有 stash
        stash_result = subprocess.run(
            ["git", "stash", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if stash_result.returncode == 0:
            result["has_stash"] = bool(stash_result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # 获取与远程的差距
        ahead_behind_result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ahead_behind_result.returncode == 0:
            parts = ahead_behind_result.stdout.strip().split()
            if len(parts) >= 2:
                result["ahead_behind"] = {
                    "behind": int(parts[0]),
                    "ahead": int(parts[1]),
                }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


def detect_todo_status() -> dict:
    """
    检测 Claude Code todos.json 状态

    Claude Code 内部 todo 格式：
    {
        "todos": [
            {"id": "...", "content": "...", "status": "in_progress|pending|completed", "priority": "high|medium|low"}
        ]
    }

    Returns:
        dict: 包含以下字段：
        - in_progress: 进行中的任务列表
        - pending: 待处理的任务列表
        - completed_today: 今天完成的任务数
        - source: todos.json 路径
    """
    result: dict[str, Any] = {
        "in_progress": [],
        "pending": [],
        "completed_today": 0,
        "source": None,
    }

    # 查找 todos.json（Claude Code 标准位置）
    possible_paths = [
        Path.cwd() / ".claude" / "todos.json",
        Path.home() / ".claude" / "todos.json",
    ]

    todos_path = None
    for path in possible_paths:
        if path.exists():
            todos_path = path
            break

    if not todos_path:
        return result

    result["source"] = str(todos_path)

    try:
        with open(todos_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        todos = data.get("todos", [])
        today = datetime.now().strftime("%Y-%m-%d")

        for todo in todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")[:100]  # 截断
            priority = todo.get("priority", "medium")
            item = {
                "id": todo.get("id", ""),
                "content": content,
                "priority": priority,
            }

            if status == "in_progress":
                result["in_progress"].append(item)
            elif status == "pending":
                result["pending"].append(item)
            elif status == "completed":
                # 检查是否今天完成
                completed_at = todo.get("completed_at", "")
                if completed_at.startswith(today):
                    result["completed_today"] += 1

    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    return result


def get_checkpoint_file(project_id: str) -> Path:
    """获取检查点存储文件路径"""
    checkpoint_dir = Path.cwd() / ".claude" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{project_id}_latest.json"


def save_checkpoint(project_id: str, verbose: bool = False) -> dict:
    """
    保存当前运行时状态到清单系统

    这是 PreCompact Hook 的核心功能：
    1. 检测运行中的端口和进程
    2. 检测 git 状态（分支、未提交变更、stash）
    3. 检测 todo 状态（进行中、待处理）
    4. 将状态写入清单系统（而不是临时文件）
    5. 同时保存到本地 JSON 文件用于 diff 比较
    6. 标记为 @runtime 标签
    """
    from backend.config import reset_config
    from backend.models.checklist import ChecklistItemCreate, ChecklistPriority, ChecklistScope
    from backend.services.checklist_service import ChecklistService

    reset_config()

    # 收集运行时状态
    ports = detect_running_ports()
    processes = detect_running_processes()
    qdrant = detect_qdrant_status()
    git_status = detect_git_status()
    todo_status = detect_todo_status()

    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "project_id": project_id,
        "ports": ports,
        "processes": processes,
        "qdrant": qdrant,
        "git_status": git_status,
        "todo_status": todo_status,
    }

    if verbose:
        print(f"📊 检测到 {len(ports)} 个端口, {len(processes)} 个进程")
        print(f"   Qdrant: {qdrant['status']}")
        print(f"   Git: {git_status['branch']} ({len(git_status['uncommitted_changes'])} uncommitted)")
        print(f"   Todos: {len(todo_status['in_progress'])} in progress, {len(todo_status['pending'])} pending")

    # 保存到本地 JSON 文件（用于 diff 比较）
    checkpoint_file = get_checkpoint_file(project_id)
    try:
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        checkpoint["checkpoint_file"] = str(checkpoint_file)
    except OSError as e:
        checkpoint["checkpoint_file_error"] = str(e)

    # 生成恢复提示
    recovery_hints = _generate_recovery_hints(checkpoint)
    checkpoint["recovery_hints"] = recovery_hints

    # 如果有需要恢复的状态，创建清单项提醒
    if ports or git_status["uncommitted_changes"] or todo_status["in_progress"]:
        service = ChecklistService()

        # 构建综合恢复提示
        content_parts = []

        if ports:
            port_list = ", ".join([f":{p['port']}" for p in ports])
            content_parts.append(f"端口 {port_list} 正在运行")

        if git_status["uncommitted_changes"]:
            change_count = len(git_status["uncommitted_changes"])
            content_parts.append(f"{change_count} 个未提交变更")

        if todo_status["in_progress"]:
            task_count = len(todo_status["in_progress"])
            content_parts.append(f"{task_count} 个进行中任务")

        if git_status["has_stash"]:
            content_parts.append("有 stash 未恢复")

        content = "⚠️ 恢复上下文：" + "；".join(content_parts)

        try:
            item = service.create_item(
                project_id=project_id,
                request=ChecklistItemCreate(
                    content=content,
                    scope=ChecklistScope.PROJECT,
                    priority=ChecklistPriority.HIGH,
                    tags=["@runtime", "@auto-checkpoint", f"session-{datetime.now().strftime('%Y%m%d')}"],
                ),
            )
            checkpoint["checklist_item_id"] = str(item.id)
            checkpoint["checklist_ref"] = item.ma_ref()

            if verbose:
                print(f"✅ 已创建清单项: {item.ma_ref()}")
        except Exception as e:
            checkpoint["error"] = str(e)
            if verbose:
                print(f"⚠️ 创建清单项失败: {e}")

    return checkpoint


def _generate_recovery_hints(checkpoint: dict) -> list[str]:
    """生成结构化的恢复提示"""
    hints = []

    # Git 相关提示
    git_status = checkpoint.get("git_status", {})
    if git_status.get("uncommitted_changes"):
        changes = git_status["uncommitted_changes"]
        modified = [c for c in changes if c["status"] in ("M", "MM")]
        added = [c for c in changes if c["status"] in ("A", "??")]
        deleted = [c for c in changes if c["status"] == "D"]

        if modified:
            hints.append(f"Git: {len(modified)} 个文件已修改未提交")
        if added:
            hints.append(f"Git: {len(added)} 个新文件待添加")
        if deleted:
            hints.append(f"Git: {len(deleted)} 个文件待删除")

    if git_status.get("has_stash"):
        hints.append("Git: 有 stash 待恢复，运行 `git stash pop`")

    ahead_behind = git_status.get("ahead_behind", {})
    if ahead_behind.get("ahead", 0) > 0:
        hints.append(f"Git: 本地领先远程 {ahead_behind['ahead']} 个提交，考虑推送")
    if ahead_behind.get("behind", 0) > 0:
        hints.append(f"Git: 本地落后远程 {ahead_behind['behind']} 个提交，考虑拉取")

    # Todo 相关提示
    todo_status = checkpoint.get("todo_status", {})
    if todo_status.get("in_progress"):
        for todo in todo_status["in_progress"][:3]:  # 最多显示3个
            hints.append(f"Todo[进行中]: {todo['content']}")

    # 端口相关提示
    ports = checkpoint.get("ports", [])
    if ports:
        port_list = ", ".join([f":{p['port']}" for p in ports])
        hints.append(f"Ports: {port_list} 正在监听")

    # Qdrant 相关提示
    qdrant = checkpoint.get("qdrant", {})
    if qdrant.get("status") == "offline":
        hints.append("Qdrant: 服务离线，记忆功能受限")

    return hints


def load_checkpoint(project_id: str) -> str:
    """
    加载恢复清单（SessionStart Hook）

    返回格式化的 Markdown，可直接注入到上下文。
    包含：
    - 系统状态（Qdrant、端口）
    - Git 状态（未提交变更提醒）
    - Todo 状态（进行中任务）
    - 上次检查点信息
    - 清单简报
    """
    from backend.config import reset_config
    from backend.models.checklist import ChecklistBriefingRequest, ChecklistScope
    from backend.services.checklist_service import ChecklistService

    reset_config()

    # 收集当前状态
    qdrant = detect_qdrant_status()
    ports = detect_running_ports()
    git_status = detect_git_status()
    todo_status = detect_todo_status()

    # 读取上次保存的检查点
    last_checkpoint = None
    checkpoint_file = get_checkpoint_file(project_id)
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                last_checkpoint = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # 构建恢复报告
    sections = []

    # Header
    sections.append(f"## Session Recovery ({datetime.now().strftime('%H:%M')})")

    # 系统状态
    qdrant_icon = "[OK]" if qdrant["status"] == "online" else "[OFFLINE]"
    sections.append(f"\n**Qdrant**: {qdrant_icon} {qdrant.get('collections_count', 0)} collections")
    port_list = ", ".join([f":{p['port']}" for p in ports]) if ports else "None"
    sections.append(f"**Active Ports**: {port_list}")

    # Git 状态（重要提醒）
    if git_status["branch"]:
        git_section = [f"\n### Git Status ({git_status['branch']})"]

        if git_status["uncommitted_changes"]:
            changes = git_status["uncommitted_changes"]
            git_section.append(f"- **{len(changes)} uncommitted changes**:")
            for change in changes[:5]:  # 最多显示5个
                status_desc = {
                    "M": "modified",
                    "A": "added",
                    "D": "deleted",
                    "??": "untracked",
                }.get(change["status"], change["status"])
                git_section.append(f"  - `{change['file']}` ({status_desc})")
            if len(changes) > 5:
                git_section.append(f"  - ... and {len(changes) - 5} more")

        if git_status["has_stash"]:
            git_section.append("- **Has stash**: Run `git stash pop` to restore")

        ahead = git_status["ahead_behind"].get("ahead", 0)
        behind = git_status["ahead_behind"].get("behind", 0)
        if ahead > 0 or behind > 0:
            git_section.append(f"- **Remote sync**: {ahead} ahead, {behind} behind")

        if git_status["last_commit"]:
            commit = git_status["last_commit"]
            git_section.append(f"- **Last commit**: `{commit['hash']}` {commit['message']}")

        if len(git_section) > 1:
            sections.extend(git_section)

    # Todo 状态
    if todo_status["in_progress"] or todo_status["pending"]:
        todo_section = ["\n### Active Tasks"]

        if todo_status["in_progress"]:
            todo_section.append(f"**In Progress ({len(todo_status['in_progress'])}):**")
            for todo in todo_status["in_progress"][:3]:
                priority_icon = {"high": "[!]", "medium": "[-]", "low": "[.]"}.get(
                    todo.get("priority", "medium"), "[-]"
                )
                todo_section.append(f"  - {priority_icon} {todo['content']}")

        if todo_status["pending"]:
            pending_count = len(todo_status["pending"])
            todo_section.append(f"**Pending**: {pending_count} tasks")

        sections.extend(todo_section)

    # 上次检查点信息
    if last_checkpoint:
        sections.append("\n### Last Checkpoint")
        sections.append(f"**Saved at**: {last_checkpoint.get('timestamp', 'Unknown')}")

        # 显示恢复提示
        recovery_hints = last_checkpoint.get("recovery_hints", [])
        if recovery_hints:
            sections.append("**Recovery hints**:")
            for hint in recovery_hints[:5]:
                sections.append(f"  - {hint}")

    sections.append("\n---")

    # 清单简报
    try:
        service = ChecklistService()
        briefing = service.get_briefing(
            ChecklistBriefingRequest(
                project_id=project_id,
                scope=ChecklistScope.PROJECT,
                limit=12,
                include_ids=True,
            )
        )
        sections.append(briefing)
    except Exception as e:
        sections.append(f"\n Checklist unavailable: {e}")

    return "\n".join(sections)


def check_status(project_id: str, as_json: bool = False) -> dict | None:
    """检查当前状态（调试用）"""

    # 收集所有状态
    qdrant = detect_qdrant_status()
    ports = detect_running_ports()
    processes = detect_running_processes()
    git_status = detect_git_status()
    todo_status = detect_todo_status()

    # 读取上次检查点
    last_checkpoint = None
    checkpoint_file = get_checkpoint_file(project_id)
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                last_checkpoint = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    status = {
        "project_id": project_id,
        "timestamp": datetime.now().isoformat(),
        "qdrant": qdrant,
        "ports": ports,
        "processes": processes[:10],  # 限制进程数量
        "git_status": git_status,
        "todo_status": todo_status,
        "last_checkpoint": {
            "timestamp": last_checkpoint.get("timestamp") if last_checkpoint else None,
            "file": str(checkpoint_file) if checkpoint_file.exists() else None,
        },
    }

    if as_json:
        return status

    # 人类可读输出
    print("=" * 50)
    print("Checkpoint Status")
    print("=" * 50)

    # Qdrant
    icon = "[OK]" if qdrant["status"] == "online" else "[X]"
    print(f"\n{icon} Qdrant: {qdrant['status']}")
    if qdrant["status"] == "online":
        print(f"   Collections: {qdrant['collections_count']}")
    else:
        print(f"   Error: {qdrant.get('error', 'unknown')}")

    # Ports
    print(f"\n[*] Active Ports: {len(ports)}")
    for p in ports:
        print(f"   :{p['port']} - {p['status']}")

    # Processes
    print(f"\n[*] Dev Processes: {len(processes)}")
    for proc in processes[:5]:
        print(f"   [{proc['type']}] PID {proc['pid']}")

    # Git Status
    print("\n[*] Git Status:")
    if git_status["branch"]:
        print(f"   Branch: {git_status['branch']}")
        if git_status["uncommitted_changes"]:
            print(f"   Uncommitted: {len(git_status['uncommitted_changes'])} files")
            for change in git_status["uncommitted_changes"][:3]:
                print(f"      {change['status']} {change['file']}")
            if len(git_status["uncommitted_changes"]) > 3:
                print(f"      ... and {len(git_status['uncommitted_changes']) - 3} more")
        if git_status["has_stash"]:
            print("   Stash: Yes (run `git stash pop` to restore)")
        if git_status["last_commit"]:
            commit = git_status["last_commit"]
            print(f"   Last commit: {commit['hash']} {commit['message'][:50]}")
    else:
        print("   Not a git repository")

    # Todo Status
    print("\n[*] Todo Status:")
    if todo_status["source"]:
        print(f"   Source: {todo_status['source']}")
        print(f"   In Progress: {len(todo_status['in_progress'])}")
        print(f"   Pending: {len(todo_status['pending'])}")
        for todo in todo_status["in_progress"][:3]:
            print(f"      -> {todo['content'][:50]}")
    else:
        print("   No todos.json found")

    # Last Checkpoint
    print("\n[*] Last Checkpoint:")
    if last_checkpoint:
        print(f"   Saved: {last_checkpoint.get('timestamp', 'Unknown')}")
        print(f"   File: {checkpoint_file}")
    else:
        print("   No checkpoint saved")

    # Checklist
    print(f"\n[*] Project Checklist: {project_id}")
    try:
        from backend.config import reset_config
        from backend.models.checklist import ChecklistBriefingRequest, ChecklistScope
        from backend.services.checklist_service import ChecklistService

        reset_config()
        service = ChecklistService()
        briefing = service.get_briefing(
            ChecklistBriefingRequest(
                project_id=project_id,
                scope=ChecklistScope.PROJECT,
                limit=5,
                include_ids=True,
            )
        )
        print(briefing)
    except Exception as e:
        print(f"   [!] Checklist unavailable: {e}")

    return None


def diff_checkpoint(project_id: str, as_json: bool = False) -> dict | None:
    """
    显示上次保存的检查点与当前状态的差异

    Returns:
        dict: 包含差异信息（如果 as_json=True）
    """
    # 读取上次检查点
    checkpoint_file = get_checkpoint_file(project_id)
    if not checkpoint_file.exists():
        if as_json:
            return {"error": "No checkpoint found", "checkpoint_file": str(checkpoint_file)}
        print(f"[!] No checkpoint found at {checkpoint_file}")
        return None

    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            last_checkpoint = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        if as_json:
            return {"error": str(e), "checkpoint_file": str(checkpoint_file)}
        print(f"[!] Failed to read checkpoint: {e}")
        return None

    # 获取当前状态
    current_ports = detect_running_ports()
    current_qdrant = detect_qdrant_status()
    current_git = detect_git_status()
    current_todo = detect_todo_status()

    # 计算差异
    diff_result: dict[str, Any] = {
        "checkpoint_timestamp": last_checkpoint.get("timestamp"),
        "current_timestamp": datetime.now().isoformat(),
        "changes": [],
    }

    # 端口变化
    last_ports = {p["port"] for p in last_checkpoint.get("ports", [])}
    current_ports_set = {p["port"] for p in current_ports}
    new_ports = current_ports_set - last_ports
    stopped_ports = last_ports - current_ports_set
    if new_ports:
        diff_result["changes"].append({
            "type": "ports",
            "action": "started",
            "items": list(new_ports),
        })
    if stopped_ports:
        diff_result["changes"].append({
            "type": "ports",
            "action": "stopped",
            "items": list(stopped_ports),
        })

    # Git 变化
    last_git: dict[str, Any] = last_checkpoint.get("git_status", {})

    # 分支变化
    if last_git.get("branch") != current_git.get("branch"):
        diff_result["changes"].append({
            "type": "git_branch",
            "from": last_git.get("branch"),
            "to": current_git.get("branch"),
        })

    # 未提交文件变化
    last_uncommitted_list: list[dict[str, Any]] = last_git.get("uncommitted_changes", [])
    current_uncommitted_list: list[dict[str, Any]] = current_git.get("uncommitted_changes", [])
    last_uncommitted = {c["file"] for c in last_uncommitted_list}
    current_uncommitted = {c["file"] for c in current_uncommitted_list}
    new_uncommitted = current_uncommitted - last_uncommitted
    resolved_uncommitted = last_uncommitted - current_uncommitted
    if new_uncommitted:
        diff_result["changes"].append({
            "type": "git_uncommitted",
            "action": "new",
            "items": list(new_uncommitted),
        })
    if resolved_uncommitted:
        diff_result["changes"].append({
            "type": "git_uncommitted",
            "action": "resolved",
            "items": list(resolved_uncommitted),
        })

    # 新提交
    last_commit: dict[str, Any] = last_git.get("last_commit") or {}
    current_commit: dict[str, Any] = current_git.get("last_commit") or {}
    if last_commit.get("hash") != current_commit.get("hash"):
        diff_result["changes"].append({
            "type": "git_commit",
            "from": last_commit.get("hash"),
            "to": current_commit.get("hash"),
            "message": current_commit.get("message"),
        })

    # Stash 变化
    if last_git.get("has_stash") != current_git.get("has_stash"):
        diff_result["changes"].append({
            "type": "git_stash",
            "from": last_git.get("has_stash"),
            "to": current_git.get("has_stash"),
        })

    # Todo 变化
    last_todo: dict[str, Any] = last_checkpoint.get("todo_status", {})

    last_in_progress_list: list[dict[str, Any]] = last_todo.get("in_progress", [])
    current_in_progress_list: list[dict[str, Any]] = current_todo.get("in_progress", [])
    last_in_progress = {t["id"] for t in last_in_progress_list}
    current_in_progress = {t["id"] for t in current_in_progress_list}
    new_in_progress = current_in_progress - last_in_progress
    completed_in_progress = last_in_progress - current_in_progress
    if new_in_progress or completed_in_progress:
        diff_result["changes"].append({
            "type": "todo_progress",
            "started": len(new_in_progress),
            "completed_or_stopped": len(completed_in_progress),
        })

    # Qdrant 变化
    last_qdrant: dict[str, Any] = last_checkpoint.get("qdrant", {})
    if last_qdrant.get("status") != current_qdrant.get("status"):
        diff_result["changes"].append({
            "type": "qdrant",
            "from": last_qdrant.get("status"),
            "to": current_qdrant.get("status"),
        })

    if as_json:
        return diff_result

    # 人类可读输出
    print("=" * 50)
    print("Checkpoint Diff")
    print("=" * 50)
    print(f"\nLast checkpoint: {diff_result['checkpoint_timestamp']}")
    print(f"Current time:    {diff_result['current_timestamp']}")
    print()

    if not diff_result["changes"]:
        print("[=] No changes detected since last checkpoint")
        return None

    print(f"[!] {len(diff_result['changes'])} change(s) detected:\n")

    for change in diff_result["changes"]:
        change_type = change["type"]

        if change_type == "ports":
            action = change["action"]
            ports_list = ", ".join([f":{p}" for p in change["items"]])
            icon = "[+]" if action == "started" else "[-]"
            print(f"{icon} Ports {action}: {ports_list}")

        elif change_type == "git_branch":
            print(f"[~] Branch changed: {change['from']} -> {change['to']}")

        elif change_type == "git_uncommitted":
            action = change["action"]
            icon = "[+]" if action == "new" else "[-]"
            files = change["items"]
            print(f"{icon} Uncommitted files ({action}): {len(files)}")
            for f in files[:3]:
                print(f"      {f}")
            if len(files) > 3:
                print(f"      ... and {len(files) - 3} more")

        elif change_type == "git_commit":
            print(f"[*] New commit: {change['to']}")
            print(f"    Message: {change['message']}")

        elif change_type == "git_stash":
            if change["to"]:
                print("[+] Stash created")
            else:
                print("[-] Stash applied/dropped")

        elif change_type == "todo_progress":
            started = change.get("started", 0)
            completed = change.get("completed_or_stopped", 0)
            if started:
                print(f"[+] {started} new task(s) in progress")
            if completed:
                print(f"[-] {completed} task(s) completed or stopped")

        elif change_type == "qdrant":
            icon = "[OK]" if change["to"] == "online" else "[X]"
            print(f"{icon} Qdrant: {change['from']} -> {change['to']}")

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Checkpoint Hook - 清单革命上下文保护",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # PreCompact Hook（保存状态）
    uv run scripts/checkpoint.py save --project 阿默斯海默症

    # SessionStart Hook（加载清单）
    uv run scripts/checkpoint.py load --project 阿默斯海默症

    # 调试状态
    uv run scripts/checkpoint.py status --project 阿默斯海默症

    # 显示与上次保存的差异
    uv run scripts/checkpoint.py diff --project 阿默斯海默症

    # JSON 输出（用于程序调用）
    uv run scripts/checkpoint.py save --project 阿默斯海默症 --json
""",
    )

    parser.add_argument(
        "action",
        choices=["save", "load", "status", "diff"],
        help="save=PreCompact保存, load=SessionStart加载, status=调试, diff=与上次对比",
    )
    parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="项目 ID（用于隔离清单）",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="JSON 输出（用于程序调用）",
    )

    args = parser.parse_args()

    if args.action == "save":
        result = save_checkpoint(args.project, args.verbose)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # 生成摘要输出
            ports = result.get("ports", [])
            git_changes = len(result.get("git_status", {}).get("uncommitted_changes", []))
            todos = len(result.get("todo_status", {}).get("in_progress", []))

            summary_parts = []
            if ports:
                summary_parts.append(f"{len(ports)} ports")
            if git_changes:
                summary_parts.append(f"{git_changes} uncommitted")
            if todos:
                summary_parts.append(f"{todos} todos")

            if summary_parts:
                summary = ", ".join(summary_parts)
                ref = result.get("checklist_ref", "N/A")
                print(f"[Checkpoint] Saved: {summary} | ref={ref}")
            else:
                print("[Checkpoint] Saved (no active state detected)")

    elif args.action == "load":
        output = load_checkpoint(args.project)
        print(output)

    elif args.action == "status":
        result = check_status(args.project, as_json=args.json)
        if args.json and result:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "diff":
        result = diff_checkpoint(args.project, as_json=args.json)
        if args.json and result:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
