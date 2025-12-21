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

设计原则（来自三方 AI 头脑风暴）：
- Plan skill = 战术层（单次任务）
- Memory Anchor = 战略层（跨会话持久）
- checkpoint.py = 桥梁（捕获运行时状态）
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

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


def save_checkpoint(project_id: str, verbose: bool = False) -> dict:
    """
    保存当前运行时状态到清单系统

    这是 PreCompact Hook 的核心功能：
    1. 检测运行中的端口和进程
    2. 将状态写入清单系统（而不是临时文件）
    3. 标记为 @runtime 标签
    """
    from backend.config import reset_config
    from backend.models.checklist import ChecklistItemCreate, ChecklistPriority, ChecklistScope
    from backend.services.checklist_service import ChecklistService

    reset_config()

    # 收集运行时状态
    ports = detect_running_ports()
    processes = detect_running_processes()
    qdrant = detect_qdrant_status()

    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "project_id": project_id,
        "ports": ports,
        "processes": processes,
        "qdrant": qdrant,
    }

    if verbose:
        print(f"📊 检测到 {len(ports)} 个端口, {len(processes)} 个进程")
        print(f"   Qdrant: {qdrant['status']}")

    # 如果有运行中的端口，创建清单项提醒
    if ports:
        service = ChecklistService()

        # 格式化端口信息
        port_list = ", ".join([f":{p['port']}" for p in ports])
        content = f"⚠️ 恢复上下文：之前有进程运行在端口 {port_list}"

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


def load_checkpoint(project_id: str) -> str:
    """
    加载恢复清单（SessionStart Hook）

    返回格式化的 Markdown，可直接注入到上下文。
    """
    from backend.config import reset_config
    from backend.models.checklist import ChecklistBriefingRequest, ChecklistScope
    from backend.services.checklist_service import ChecklistService

    reset_config()

    try:
        service = ChecklistService()

        # 获取清单简报
        briefing = service.get_briefing(
            ChecklistBriefingRequest(
                project_id=project_id,
                scope=ChecklistScope.PROJECT,
                limit=12,
                include_ids=True,
            )
        )

        # 添加运行时恢复提示
        qdrant = detect_qdrant_status()
        ports = detect_running_ports()

        header = f"""## 🔄 Session Recovery ({datetime.now().strftime('%H:%M')})

**Qdrant**: {qdrant['status']} ({qdrant.get('collections_count', 0)} collections)
**Active Ports**: {', '.join([f":{p['port']}" for p in ports]) or 'None detected'}

---

"""
        return header + briefing

    except Exception as e:
        return f"""## 🔄 Session Recovery

⚠️ 无法加载清单: {e}

**Qdrant**: {detect_qdrant_status()['status']}
"""


def check_status(project_id: str) -> None:
    """检查当前状态（调试用）"""
    print("=" * 50)
    print("Checkpoint Status")
    print("=" * 50)

    # Qdrant
    qdrant = detect_qdrant_status()
    icon = "✅" if qdrant["status"] == "online" else "❌"
    print(f"\n{icon} Qdrant: {qdrant['status']}")
    if qdrant["status"] == "online":
        print(f"   Collections: {qdrant['collections_count']}")
    else:
        print(f"   Error: {qdrant.get('error', 'unknown')}")

    # Ports
    ports = detect_running_ports()
    print(f"\n🔌 Active Ports: {len(ports)}")
    for p in ports:
        print(f"   :{p['port']} - {p['status']}")

    # Processes
    processes = detect_running_processes()
    print(f"\n⚙️ Dev Processes: {len(processes)}")
    for proc in processes[:5]:  # 只显示前5个
        print(f"   [{proc['type']}] PID {proc['pid']}")

    # Checklist
    print(f"\n📋 Project: {project_id}")
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
        print(f"   ⚠️ 无法加载清单: {e}")


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
""",
    )

    parser.add_argument(
        "action",
        choices=["save", "load", "status"],
        help="save=PreCompact保存, load=SessionStart加载, status=调试",
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
            ports = result.get("ports", [])
            if ports:
                print(f"[Checkpoint] Saved: {len(ports)} ports, ref={result.get('checklist_ref', 'N/A')}")
            else:
                print("[Checkpoint] No active ports detected")

    elif args.action == "load":
        output = load_checkpoint(args.project)
        print(output)

    elif args.action == "status":
        check_status(args.project)


if __name__ == "__main__":
    main()
