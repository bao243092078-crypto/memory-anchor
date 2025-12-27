"""Projects API - 项目列表和切换接口"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import DEFAULT_GLOBAL_CONFIG_DIR, get_config

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectInfo(BaseModel):
    """项目信息"""
    id: str
    name: str
    type: str
    has_constitution: bool
    memory_count: Optional[int] = None


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: list[ProjectInfo]
    current_project: str


class SwitchProjectRequest(BaseModel):
    """切换项目请求"""
    project_id: str


class SwitchProjectResponse(BaseModel):
    """切换项目响应"""
    success: bool
    project_id: str
    message: str


@router.get("", response_model=ProjectListResponse)
async def list_projects() -> ProjectListResponse:
    """
    获取可用项目列表

    返回所有在 ~/.memory-anchor/projects/ 下的项目
    """
    projects_dir = DEFAULT_GLOBAL_CONFIG_DIR / "projects"

    if not projects_dir.exists():
        return ProjectListResponse(projects=[], current_project="default")

    projects: list[ProjectInfo] = []

    # 排除以下目录
    exclude_dirs = {"_archived", "_data", "global", "remotes"}

    for project_path in sorted(projects_dir.iterdir()):
        if not project_path.is_dir():
            continue

        project_id = project_path.name

        # 跳过排除目录
        if project_id in exclude_dirs:
            continue

        # 检查是否有 constitution.yaml
        constitution_path = project_path / "constitution.yaml"
        has_constitution = constitution_path.exists()

        # 读取项目配置
        config_path = project_path / "config.yaml"
        project_name = project_id
        project_type = "ai-development"

        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    project_name = cfg.get("project", {}).get("name", project_id)
                    project_type = cfg.get("project", {}).get("type", "ai-development")
            except Exception:
                pass

        projects.append(ProjectInfo(
            id=project_id,
            name=project_name,
            type=project_type,
            has_constitution=has_constitution,
        ))

    # 获取当前项目
    current_project = os.getenv("MCP_MEMORY_PROJECT_ID", "default")

    return ProjectListResponse(
        projects=projects,
        current_project=current_project,
    )


@router.get("/current")
async def get_current_project() -> dict:
    """
    获取当前项目信息
    """
    config = get_config()
    return {
        "project_id": config.project_name,
        "project_type": config.project_type,
        "data_dir": str(config.data_dir),
        "collection_name": config.collection_name,
    }


@router.post("/switch", response_model=SwitchProjectResponse)
async def switch_project(request: SwitchProjectRequest) -> SwitchProjectResponse:
    """
    切换当前项目

    注意：这只是一个提示性接口，实际的项目隔离是通过 MCP_MEMORY_PROJECT_ID 环境变量控制的。
    前端应该在收到成功响应后刷新页面或重新初始化。
    """
    project_id = request.project_id.strip()

    if not project_id:
        raise HTTPException(status_code=400, detail="项目 ID 不能为空")

    # 检查项目是否存在
    project_path = DEFAULT_GLOBAL_CONFIG_DIR / "projects" / project_id

    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"项目 '{project_id}' 不存在。请先运行 `./ma init --project {project_id}` 初始化项目。"
        )

    return SwitchProjectResponse(
        success=True,
        project_id=project_id,
        message=f"请将 MCP_MEMORY_PROJECT_ID 设置为 '{project_id}' 并重启服务以切换项目。",
    )
