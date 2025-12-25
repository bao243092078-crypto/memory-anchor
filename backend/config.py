"""
Memory Anchor Configuration - 配置管理模块

支持三种配置来源（优先级从高到低）：
1. 环境变量（覆盖所有配置）
2. 项目配置文件（.memory-anchor/config.yaml）
3. 全局配置文件（~/.memory-anchor/config.yaml）
4. 默认值

用法：
    from backend.config import get_config
    config = get_config()
    print(config.project_name)
    print(config.qdrant_path)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# 默认全局配置目录
DEFAULT_GLOBAL_CONFIG_DIR = Path.home() / ".memory-anchor"


class ConfigLoadError(Exception):
    """配置加载错误"""

    pass
DEFAULT_PROJECT_CONFIG_DIR = Path(".memory-anchor")


@dataclass
class CloudSyncConfig:
    """云端同步配置"""
    enabled: bool = False
    provider: str = "s3"  # s3 | r2 | minio
    bucket: str = ""
    region: str = "us-east-1"
    endpoint_url: Optional[str] = None  # MinIO/R2 自定义端点
    prefix: str = ""  # 存储路径前缀

    # 加密配置
    encryption_enabled: bool = True
    encryption_key_path: Path = field(default_factory=lambda: DEFAULT_GLOBAL_CONFIG_DIR / "encryption.key")

    # 同步策略
    auto_sync: bool = False  # 会话结束时自动同步
    conflict_strategy: str = "lww"  # lww (Last-Write-Wins) | manual

    # AWS 凭证（优先使用环境变量 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None


@dataclass
class ConstitutionItem:
    """宪法层条目"""
    id: str
    content: str
    category: Optional[str] = None


@dataclass
class MemoryAnchorConfig:
    """Memory Anchor 配置"""

    # === 项目信息 ===
    project_name: str = "default"
    project_type: str = "ai-development"  # patient-care | ai-development | knowledge-base

    # === 存储路径 ===
    data_dir: Path = field(default_factory=lambda: DEFAULT_GLOBAL_CONFIG_DIR / "projects" / "default")
    qdrant_path: Path = field(default_factory=lambda: Path(".qdrant"))
    qdrant_url: Optional[str] = None  # None 表示使用本地模式
    sqlite_path: Path = field(default_factory=lambda: Path(".memos") / "constitution_changes.db")

    # === Qdrant 配置 ===
    collection_prefix: str = "memory_anchor_notes"
    vector_size: int = 384  # paraphrase-multilingual-MiniLM-L12-v2

    # === 记忆配置 ===
    max_constitution_items: int = 20
    min_search_score: float = 0.3
    session_expire_hours: int = 24
    require_approval_threshold: float = 0.9
    approvals_needed: int = 3

    # === LLM 配置（Memory Refiner 使用） ===
    llm_provider: Optional[str] = None  # anthropic | openai | local
    llm_enabled: bool = True  # 是否启用 LLM 精炼功能
    refiner_keep_recent: int = 3  # Observation Masking: 保留最近 N 条完整记忆
    refiner_max_tokens: int = 500  # 精炼输出的最大 token 数

    # === 阈值配置（Phase 4） ===
    plans_max_lines: int = 200  # PLAN.md 最大行数（超过则警告）
    session_log_max_lines: int = 500  # 会话日志最大行数
    summary_max_files: int = 5  # 会话摘要中显示的最大文件数
    summary_max_todos: int = 5  # 会话摘要中显示的最大 TODO 数
    todo_content_max_chars: int = 50  # TODO 内容最大字符数（截断）
    checklist_max_items: int = 20  # 清单简报最大条目数
    memory_content_max_chars: int = 500  # Memory Anchor 写入内容最大字符数

    # === 宪法层条目（从 yaml 加载） ===
    constitution: list[ConstitutionItem] = field(default_factory=list)

    # === 云端同步配置 ===
    cloud: CloudSyncConfig = field(default_factory=CloudSyncConfig)

    @property
    def collection_name(self) -> str:
        """获取 Qdrant collection 名称

        优先级：
        1. 环境变量 MEMORY_ANCHOR_COLLECTION（用于测试隔离）
        2. 根据 project_name 生成
        """
        # 测试隔离：优先使用环境变量
        env_collection = os.environ.get("MEMORY_ANCHOR_COLLECTION")
        if env_collection:
            return env_collection

        # 安全过滤项目名
        safe_name = "".join(c for c in self.project_name if c.isalnum() or c in ("_", "-"))
        if not safe_name or safe_name == "default":
            return self.collection_prefix
        return f"{self.collection_prefix}_{safe_name}"

    @property
    def constitution_yaml_path(self) -> Path:
        """宪法层配置文件路径"""
        return self.data_dir / "constitution.yaml"

    def ensure_directories(self):
        """确保所有必要目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.qdrant_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


def _load_yaml_config(path: Path) -> dict:
    """
    加载 YAML 配置文件。

    Args:
        path: 配置文件路径

    Returns:
        配置字典，如果文件不存在则返回空字典

    Raises:
        ConfigLoadError: YAML 解析失败或其他错误
    """
    if not path.exists():
        logger.debug(f"Config file not found: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content or {}
    except FileNotFoundError:
        # 文件在 exists() 检查后被删除（罕见情况）
        logger.debug(f"Config file disappeared: {path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in {path}: {e}")
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e
    except Exception as e:
        logger.error(f"Failed to load config from {path}: {e}")
        raise ConfigLoadError(f"Failed to load config from {path}: {e}") from e


def _load_cloud_config(merged: dict) -> CloudSyncConfig:
    """
    从合并后的配置字典加载云端同步配置。

    Args:
        merged: 已合并的配置字典

    Returns:
        CloudSyncConfig 对象
    """
    cloud_cfg = merged.get("cloud", {})

    # 环境变量覆盖（MA_CLOUD_ 前缀）
    env_overrides = {
        "enabled": os.getenv("MA_CLOUD_ENABLED"),
        "provider": os.getenv("MA_CLOUD_PROVIDER"),
        "bucket": os.getenv("MA_CLOUD_BUCKET"),
        "region": os.getenv("MA_CLOUD_REGION"),
        "endpoint_url": os.getenv("MA_CLOUD_ENDPOINT_URL"),
        "prefix": os.getenv("MA_CLOUD_PREFIX"),
        "encryption_enabled": os.getenv("MA_CLOUD_ENCRYPTION_ENABLED"),
        "encryption_key_path": os.getenv("MA_CLOUD_ENCRYPTION_KEY_PATH"),
        "auto_sync": os.getenv("MA_CLOUD_AUTO_SYNC"),
        "conflict_strategy": os.getenv("MA_CLOUD_CONFLICT_STRATEGY"),
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("MA_CLOUD_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("MA_CLOUD_SECRET_ACCESS_KEY"),
    }

    for key, value in env_overrides.items():
        if value is not None:
            cloud_cfg[key] = value

    # 布尔值转换
    for bool_key in ("enabled", "encryption_enabled", "auto_sync"):
        if bool_key in cloud_cfg and isinstance(cloud_cfg[bool_key], str):
            cloud_cfg[bool_key] = cloud_cfg[bool_key].lower() in ("true", "1", "yes")

    # Path 转换
    if "encryption_key_path" in cloud_cfg and isinstance(cloud_cfg["encryption_key_path"], str):
        cloud_cfg["encryption_key_path"] = Path(cloud_cfg["encryption_key_path"]).expanduser()

    return CloudSyncConfig(
        enabled=cloud_cfg.get("enabled", False),
        provider=cloud_cfg.get("provider", "s3"),
        bucket=cloud_cfg.get("bucket", ""),
        region=cloud_cfg.get("region", "us-east-1"),
        endpoint_url=cloud_cfg.get("endpoint_url"),
        prefix=cloud_cfg.get("prefix", ""),
        encryption_enabled=cloud_cfg.get("encryption_enabled", True),
        encryption_key_path=cloud_cfg.get("encryption_key_path", DEFAULT_GLOBAL_CONFIG_DIR / "encryption.key"),
        auto_sync=cloud_cfg.get("auto_sync", False),
        conflict_strategy=cloud_cfg.get("conflict_strategy", "lww"),
        access_key_id=cloud_cfg.get("access_key_id"),
        secret_access_key=cloud_cfg.get("secret_access_key"),
    )


def _load_constitution_yaml(path: Path) -> list[ConstitutionItem]:
    """
    从 constitution.yaml 加载宪法层条目。

    Args:
        path: constitution.yaml 文件路径

    Returns:
        宪法层条目列表，如果文件不存在则返回空列表

    Raises:
        ConfigLoadError: YAML 解析失败或其他错误
    """
    if not path.exists():
        logger.debug(f"Constitution file not found: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        items = data.get("constitution", [])
        return [
            ConstitutionItem(
                id=item.get("id", f"item-{i}"),
                content=item.get("content", ""),
                category=item.get("category"),
            )
            for i, item in enumerate(items)
            if item.get("content")
        ]
    except FileNotFoundError:
        # 文件在 exists() 检查后被删除（罕见情况）
        logger.debug(f"Constitution file disappeared: {path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in {path}: {e}")
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e
    except Exception as e:
        logger.error(f"Failed to load constitution from {path}: {e}")
        raise ConfigLoadError(f"Failed to load constitution from {path}: {e}") from e


def load_config(
    project_id: Optional[str] = None,
    config_dir: Optional[Path] = None,
) -> MemoryAnchorConfig:
    """
    加载配置

    Args:
        project_id: 项目 ID（用于隔离不同项目的数据）
        config_dir: 配置目录（默认 ~/.memory-anchor）

    Returns:
        配置对象
    """
    # 1. 确定配置目录
    global_config_dir = config_dir or DEFAULT_GLOBAL_CONFIG_DIR

    # 2. 确定项目 ID（优先级：参数 > 环境变量 > 默认）
    project: str = project_id or os.getenv("MCP_MEMORY_PROJECT_ID") or "default"

    # 3. 确定数据目录
    data_dir = global_config_dir / "projects" / project

    # 4. 加载全局配置
    global_config_path = global_config_dir / "config.yaml"
    global_cfg = _load_yaml_config(global_config_path)

    # 5. 加载项目配置
    project_config_path = data_dir / "config.yaml"
    project_cfg = _load_yaml_config(project_config_path)

    # 6. 合并配置（项目覆盖全局）
    merged = {**global_cfg, **project_cfg}

    # 7. 环境变量覆盖（QDRANT_URL 无默认值，None 表示本地模式）
    env_overrides = {
        "qdrant_url": os.getenv("QDRANT_URL"),  # None = local mode
        "project_name": os.getenv("MCP_MEMORY_PROJECT_ID"),
        "llm_provider": os.getenv("LLM_PROVIDER"),
    }

    for key, value in env_overrides.items():
        if value:
            merged[key] = value

    # LLM_ENABLED 环境变量特殊处理（布尔值）
    llm_enabled_env = os.getenv("LLM_ENABLED")
    if llm_enabled_env is not None:
        merged["llm_enabled"] = llm_enabled_env.lower() in ("true", "1", "yes")

    # 阈值环境变量覆盖（MA_ 前缀，整数类型）
    threshold_env_mapping = {
        "plans_max_lines": "MA_PLANS_MAX_LINES",
        "session_log_max_lines": "MA_SESSION_LOG_MAX_LINES",
        "summary_max_files": "MA_SUMMARY_MAX_FILES",
        "summary_max_todos": "MA_SUMMARY_MAX_TODOS",
        "todo_content_max_chars": "MA_TODO_CONTENT_MAX_CHARS",
        "checklist_max_items": "MA_CHECKLIST_MAX_ITEMS",
        "memory_content_max_chars": "MA_MEMORY_CONTENT_MAX_CHARS",
    }

    for config_key, env_key in threshold_env_mapping.items():
        env_value = os.getenv(env_key)
        if env_value is not None:
            try:
                merged[config_key] = int(env_value)
            except ValueError:
                logger.warning(f"Invalid integer value for {env_key}: {env_value}")

    # qdrant_path 优先级：
    # 1) 显式配置（config.yaml / env）
    # 2) 默认使用全局项目数据目录（多项目隔离，避免 cwd 变化导致“换了个大脑”）
    qdrant_path_override = merged.get("qdrant_path") or os.getenv("MCP_MEMORY_QDRANT_PATH")
    if qdrant_path_override:
        qdrant_path = Path(str(qdrant_path_override)).expanduser()
    else:
        qdrant_path = data_dir / ".qdrant"

    # sqlite_path 优先级：
    # 1) 显式配置（config.yaml / env）
    # 2) 当前工作目录已有 .memos/constitution_changes.db（开发/仓库模式，避免“丢数据”）
    # 3) 默认使用全局项目数据目录（多项目隔离）
    sqlite_path_override = merged.get("sqlite_path") or os.getenv("MCP_MEMORY_SQLITE_PATH")
    if sqlite_path_override:
        sqlite_path = Path(str(sqlite_path_override)).expanduser()
    else:
        local_sqlite = Path(".memos") / "constitution_changes.db"
        sqlite_path = local_sqlite if local_sqlite.exists() else (data_dir / "constitution_changes.db")

    # 8. 构建配置对象
    project_name = merged.get("project_name") or project
    config = MemoryAnchorConfig(
        project_name=project_name,
        project_type=merged.get("project_type", "ai-development"),
        data_dir=data_dir,
        qdrant_path=qdrant_path,
        qdrant_url=merged.get("qdrant_url"),
        sqlite_path=sqlite_path,
        collection_prefix=merged.get("collection_prefix", "memory_anchor_notes"),
        vector_size=merged.get("vector_size", 384),
        max_constitution_items=merged.get("max_constitution_items", 20),
        min_search_score=merged.get("min_search_score", 0.3),
        session_expire_hours=merged.get("session_expire_hours", 24),
        require_approval_threshold=merged.get("require_approval_threshold", 0.9),
        approvals_needed=merged.get("approvals_needed", 3),
        # LLM 配置
        llm_provider=merged.get("llm_provider"),
        llm_enabled=merged.get("llm_enabled", True),
        refiner_keep_recent=merged.get("refiner_keep_recent", 3),
        refiner_max_tokens=merged.get("refiner_max_tokens", 500),
        # 阈值配置
        plans_max_lines=merged.get("plans_max_lines", 200),
        session_log_max_lines=merged.get("session_log_max_lines", 500),
        summary_max_files=merged.get("summary_max_files", 5),
        summary_max_todos=merged.get("summary_max_todos", 5),
        todo_content_max_chars=merged.get("todo_content_max_chars", 50),
        checklist_max_items=merged.get("checklist_max_items", 20),
        memory_content_max_chars=merged.get("memory_content_max_chars", 500),
        # 云端同步配置
        cloud=_load_cloud_config(merged),
    )

    # 9. 加载宪法层条目
    constitution_path = data_dir / "constitution.yaml"
    config.constitution = _load_constitution_yaml(constitution_path)

    return config


# === 全局单例 ===
_config: Optional[MemoryAnchorConfig] = None


def get_config(
    project_id: Optional[str] = None,
    force_reload: bool = False,
) -> MemoryAnchorConfig:
    """
    获取配置单例

    Args:
        project_id: 项目 ID
        force_reload: 强制重新加载

    Returns:
        配置对象
    """
    global _config

    if _config is None or force_reload:
        _config = load_config(project_id=project_id)

    return _config


def reset_config():
    """重置配置单例（用于测试）"""
    global _config
    _config = None


def create_default_constitution_yaml(path: Path, project_type: str = "ai-development"):
    """
    创建默认的 constitution.yaml 文件

    Args:
        path: 文件路径
        project_type: 项目类型
    """
    templates = {
        "ai-development": {
            "version": 1,
            "project": {
                "name": "My AI Project",
                "type": "ai-development",
            },
            "constitution": [
                {
                    "id": "philosophy",
                    "category": "item",
                    "content": "把 AI 当作阿尔茨海默症患者——能力强但易失忆，Memory Anchor 是 AI 的外挂海马体",
                },
                {
                    "id": "memory-model",
                    "category": "routine",
                    "content": "三层记忆模型：宪法层（核心身份）→ 事实层（长期记忆）→ 会话层（短期记忆）",
                },
            ],
            "settings": {
                "max_constitution_items": 20,
                "min_search_score": 0.3,
                "session_expire_hours": 24,
            },
        },
        "patient-care": {
            "version": 1,
            "project": {
                "name": "患者记忆辅助",
                "type": "patient-care",
            },
            "constitution": [
                {
                    "id": "patient-name",
                    "category": "person",
                    "content": "患者姓名：[请填写]",
                },
                {
                    "id": "emergency-contact",
                    "category": "person",
                    "content": "紧急联系人：[请填写姓名和电话]",
                },
            ],
            "settings": {
                "max_constitution_items": 20,
                "min_search_score": 0.3,
                "session_expire_hours": 24,
            },
        },
        "knowledge-base": {
            "version": 1,
            "project": {
                "name": "个人知识库",
                "type": "knowledge-base",
            },
            "constitution": [
                {
                    "id": "user-identity",
                    "category": "person",
                    "content": "知识库所有者：[请填写]",
                },
            ],
            "settings": {
                "max_constitution_items": 50,
                "min_search_score": 0.2,
                "session_expire_hours": 168,  # 7 days
            },
        },
    }

    template = templates.get(project_type, templates["ai-development"])

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


__all__ = [
    "MemoryAnchorConfig",
    "CloudSyncConfig",
    "ConstitutionItem",
    "ConfigLoadError",
    "get_config",
    "load_config",
    "reset_config",
    "create_default_constitution_yaml",
]
