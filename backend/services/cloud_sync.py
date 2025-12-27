"""
Cloud Sync Service - 云端同步核心服务

提供记忆的导出、导入和同步功能。

核心组件：
- MemoryExporter: 将 Qdrant 记忆导出为 JSONL
- MemoryImporter: 将 JSONL 导入到 Qdrant
- CloudSyncService: 编排同步流程

数据格式：
- memories.jsonl: 每行一条记忆
- constitution.json: L0 宪法层
- manifest.json: 同步清单（版本、时间戳、校验和）
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterator, Optional
from uuid import UUID, uuid4

from backend.config import CloudSyncConfig, load_config
from backend.models.note import MemoryLayer
from backend.services.cloud_storage import CloudStorageBackend, create_storage_backend
from backend.services.data_encryptor import DataEncryptor, EncryptionError

logger = logging.getLogger(__name__)


@dataclass
class SyncManifest:
    """同步清单 - 记录同步状态"""

    version: str = "1.0.0"
    project_id: str = ""
    last_sync: str = ""  # ISO 8601
    memories_count: int = 0
    memories_checksum: str = ""  # SHA-256
    constitution_checksum: str = ""
    encrypted: bool = False

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "SyncManifest":
        """从 JSON 反序列化"""
        return cls(**json.loads(data))


@dataclass
class MemoryRecord:
    """记忆记录 - JSONL 行格式"""

    id: str
    content: str
    layer: str
    category: Optional[str] = None
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_json_line(self) -> str:
        """序列化为 JSON 行"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> "MemoryRecord":
        """从 JSON 行反序列化"""
        data = json.loads(line)
        return cls(**data)


class MemoryExporter:
    """记忆导出器 - 从 Qdrant 导出到 JSONL"""

    def __init__(self, project_id: str):
        """初始化导出器

        Args:
            project_id: 项目 ID
        """
        self.project_id = project_id
        self._search_service = None

    def _get_search_service(self):
        """延迟获取 SearchService"""
        if self._search_service is None:
            from backend.services.search import get_search_service

            self._search_service = get_search_service()
        return self._search_service

    def export_memories(self, layers: Optional[list[str]] = None) -> Iterator[MemoryRecord]:
        """导出记忆

        Args:
            layers: 要导出的层级列表，None 表示全部

        Yields:
            MemoryRecord 对象
        """
        search_service = self._get_search_service()
        normalized_layers: Optional[list[str]] = None
        if layers is not None:
            normalized_layers = []
            for layer in layers:
                try:
                    normalized_layers.append(MemoryLayer.from_string(str(layer)).value)
                except ValueError:
                    continue

        # 导出所有记忆（使用空查询获取全部）
        # 分批获取以支持大量数据
        batch_size = 100
        offset = None

        while True:
            # 使用 scroll API 或分页获取
            records, next_offset = search_service.scroll(
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not records:
                break

            for point in records:
                payload = point.payload or {}

                # 过滤层级
                raw_layer = payload.get("layer", MemoryLayer.VERIFIED_FACT.value)
                try:
                    layer = MemoryLayer.from_string(str(raw_layer)).value
                except ValueError:
                    layer = MemoryLayer.VERIFIED_FACT.value
                if normalized_layers is not None and layer not in normalized_layers:
                    continue

                yield MemoryRecord(
                    id=str(point.id),
                    content=payload.get("content", ""),
                    layer=layer,
                    category=payload.get("category"),
                    confidence=payload.get("confidence", 1.0),
                    created_at=payload.get("created_at", ""),
                    updated_at=payload.get("updated_at", ""),
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("content", "layer", "category", "confidence", "created_at", "updated_at")
                    },
                )

            if next_offset is None:
                break
            offset = next_offset

    def export_to_jsonl(self, output: BytesIO, layers: Optional[list[str]] = None) -> tuple[int, str]:
        """导出到 JSONL 格式

        Args:
            output: 输出流
            layers: 要导出的层级

        Returns:
            (记忆数量, SHA-256 校验和)
        """
        hasher = hashlib.sha256()
        count = 0

        for record in self.export_memories(layers):
            line = record.to_json_line() + "\n"
            line_bytes = line.encode("utf-8")
            output.write(line_bytes)
            hasher.update(line_bytes)
            count += 1

        return count, hasher.hexdigest()

    def export_constitution(self) -> tuple[str, str]:
        """导出宪法层

        Returns:
            (JSON 内容, SHA-256 校验和)
        """
        from backend.core.memory_kernel import get_memory_kernel

        kernel = get_memory_kernel()
        entries = kernel.get_constitution()

        data = {
            "version": "1.0.0",
            "project_id": self.project_id,
            "entries": [
                {
                    "id": str(entry.get("id")),
                    "content": entry.get("content"),
                    "category": entry.get("category"),
                    "created_at": (
                        entry.get("created_at").isoformat()
                        if isinstance(entry.get("created_at"), datetime)
                        else entry.get("created_at")
                    ),
                }
                for entry in entries
            ],
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        checksum = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        return json_str, checksum


class MemoryImporter:
    """记忆导入器 - 从 JSONL 导入到 Qdrant"""

    def __init__(self, project_id: str):
        """初始化导入器

        Args:
            project_id: 项目 ID
        """
        self.project_id = project_id
        self._search_service = None

    def _get_search_service(self):
        """延迟获取 SearchService"""
        if self._search_service is None:
            from backend.services.search import get_search_service

            self._search_service = get_search_service()
        return self._search_service

    def import_from_jsonl(
        self,
        data: bytes,
        strategy: str = "lww",
        expected_checksum: Optional[str] = None,
    ) -> tuple[int, int, int]:
        """从 JSONL 导入

        Args:
            data: JSONL 数据
            strategy: 冲突策略 (lww: Last-Write-Wins, skip: 跳过已存在, merge: 合并)
            expected_checksum: 期望的校验和（可选）

        Returns:
            (导入数量, 跳过数量, 冲突数量)

        Raises:
            ValueError: 校验和不匹配
        """
        # 验证校验和
        if expected_checksum:
            actual_checksum = hashlib.sha256(data).hexdigest()
            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
                )

        search_service = self._get_search_service()

        imported = 0
        skipped = 0
        conflicts = 0

        for line in data.decode("utf-8").strip().split("\n"):
            if not line:
                continue

            record = MemoryRecord.from_json_line(line)

            # 规范化 layer
            if record.layer:
                try:
                    layer_value = MemoryLayer.from_string(record.layer).value
                except ValueError:
                    layer_value = MemoryLayer.VERIFIED_FACT.value
            else:
                layer_value = MemoryLayer.VERIFIED_FACT.value

            # 规范化 ID
            original_id = record.id
            try:
                note_id = UUID(str(record.id))
                id_regenerated = False
            except (ValueError, TypeError):
                note_id = uuid4()
                id_regenerated = True

            metadata = record.metadata or {}

            # 检查是否已存在
            existing = search_service.get_note(note_id)

            if existing:
                if strategy == "skip":
                    skipped += 1
                    continue
                elif strategy == "lww":
                    # Last-Write-Wins: 比较更新时间
                    existing_updated = str(existing.get("updated_at") or "")
                    record_updated = str(record.updated_at or "")
                    if record_updated and existing_updated and record_updated <= existing_updated:
                        skipped += 1
                        continue
                    conflicts += 1
                elif strategy == "merge":
                    # TODO: 实现合并逻辑
                    conflicts += 1
                    continue

            if id_regenerated:
                metadata["original_id"] = str(original_id)

            created_at = record.created_at or metadata.get("created_at")
            updated_at = record.updated_at or metadata.get("updated_at")

            search_service.index_note(
                note_id=note_id,
                content=record.content,
                layer=layer_value,
                category=record.category,
                is_active=metadata.get("is_active", True),
                confidence=record.confidence,
                source=metadata.get("source"),
                agent_id=metadata.get("agent_id"),
                created_at=created_at or None,
                updated_at=updated_at or None,
                expires_at=metadata.get("expires_at"),
                priority=metadata.get("priority"),
                created_by=metadata.get("created_by"),
                last_verified=metadata.get("last_verified"),
                metadata=metadata,
                event_when=metadata.get("event_when"),
                event_where=metadata.get("event_where"),
                event_who=metadata.get("event_who"),
            )
            imported += 1

        return imported, skipped, conflicts

    def verify_integrity(self, data: bytes, expected_checksum: str) -> bool:
        """验证数据完整性

        Args:
            data: 数据
            expected_checksum: 期望的 SHA-256 校验和

        Returns:
            是否匹配
        """
        actual = hashlib.sha256(data).hexdigest()
        return actual == expected_checksum


class CloudSyncService:
    """云端同步服务 - 编排导出/导入/同步"""

    def __init__(
        self,
        project_id: str,
        config: Optional[CloudSyncConfig] = None,
        storage: Optional[CloudStorageBackend] = None,
        encryptor: Optional[DataEncryptor] = None,
    ):
        """初始化同步服务

        Args:
            project_id: 项目 ID
            config: 云端同步配置（默认从配置文件加载）
            storage: 存储后端（默认根据配置创建）
            encryptor: 加密器（默认根据配置创建）
        """
        self.project_id = project_id
        self.config = config or load_config().cloud

        if not self.config.enabled:
            logger.warning("Cloud sync is disabled in configuration")

        # 初始化存储后端
        if storage:
            self.storage = storage
        elif self.config.bucket:
            self.storage = create_storage_backend(
                provider=self.config.provider,
                bucket=self.config.bucket,
                region=self.config.region,
                endpoint_url=self.config.endpoint_url,
                access_key_id=self.config.access_key_id,
                secret_access_key=self.config.secret_access_key,
                prefix=self.config.prefix or project_id,
            )
        else:
            self.storage = None

        # 初始化加密器
        if encryptor:
            self.encryptor = encryptor
        elif self.config.encryption_enabled and self.config.encryption_key_path.exists():
            self.encryptor = DataEncryptor(key_path=self.config.encryption_key_path)
        else:
            self.encryptor = None

        self.exporter = MemoryExporter(project_id)
        self.importer = MemoryImporter(project_id)

    def _get_remote_path(self, filename: str) -> str:
        """获取远端文件路径"""
        return f"{self.project_id}/{filename}"

    def push(self, encrypt: bool = True) -> SyncManifest:
        """推送到云端

        Args:
            encrypt: 是否加密

        Returns:
            同步清单

        Raises:
            RuntimeError: 推送失败
        """
        if not self.storage:
            raise RuntimeError("Cloud storage not configured")

        # 1. 导出记忆到 JSONL
        memories_buffer = BytesIO()
        count, memories_checksum = self.exporter.export_to_jsonl(memories_buffer)
        memories_data = memories_buffer.getvalue()

        # 2. 导出宪法层
        constitution_json, constitution_checksum = self.exporter.export_constitution()
        constitution_data = constitution_json.encode("utf-8")

        # 3. 加密（如果启用）
        encrypted = False
        if encrypt and self.encryptor:
            memories_data = self.encryptor.encrypt(memories_data)
            constitution_data = self.encryptor.encrypt(constitution_data)
            encrypted = True

        # 4. 上传
        memories_filename = "memories.jsonl.enc" if encrypted else "memories.jsonl"
        constitution_filename = "constitution.json.enc" if encrypted else "constitution.json"

        if not self.storage.upload(self._get_remote_path(memories_filename), memories_data):
            raise RuntimeError("Failed to upload memories")

        if not self.storage.upload(self._get_remote_path(constitution_filename), constitution_data):
            raise RuntimeError("Failed to upload constitution")

        # 5. 生成并上传清单
        manifest = SyncManifest(
            version="1.0.0",
            project_id=self.project_id,
            last_sync=datetime.now(timezone.utc).isoformat(),
            memories_count=count,
            memories_checksum=memories_checksum,
            constitution_checksum=constitution_checksum,
            encrypted=encrypted,
        )

        manifest_data = manifest.to_json().encode("utf-8")
        if not self.storage.upload(self._get_remote_path("manifest.json"), manifest_data):
            raise RuntimeError("Failed to upload manifest")

        logger.info(f"Pushed {count} memories to cloud (encrypted={encrypted})")
        return manifest

    def pull(self, strategy: str = "lww") -> tuple[int, int, int]:
        """从云端拉取

        Args:
            strategy: 冲突策略 (lww/skip/merge)

        Returns:
            (导入数量, 跳过数量, 冲突数量)

        Raises:
            RuntimeError: 拉取失败
        """
        if not self.storage:
            raise RuntimeError("Cloud storage not configured")

        # 1. 下载清单
        manifest_data = self.storage.download(self._get_remote_path("manifest.json"))
        if not manifest_data:
            raise RuntimeError("Manifest not found on remote")

        manifest = SyncManifest.from_json(manifest_data.decode("utf-8"))

        # 2. 下载记忆
        memories_filename = "memories.jsonl.enc" if manifest.encrypted else "memories.jsonl"
        memories_data = self.storage.download(self._get_remote_path(memories_filename))
        if not memories_data:
            raise RuntimeError("Memories file not found on remote")

        # 3. 解密（如果加密）
        if manifest.encrypted:
            if not self.encryptor:
                raise RuntimeError("Data is encrypted but no encryption key available")
            try:
                memories_data = self.encryptor.decrypt(memories_data)
            except EncryptionError as e:
                raise RuntimeError(f"Failed to decrypt memories: {e}") from e

        # 4. 导入
        imported, skipped, conflicts = self.importer.import_from_jsonl(
            memories_data,
            strategy=strategy,
            expected_checksum=manifest.memories_checksum,
        )

        logger.info(f"Pulled from cloud: imported={imported}, skipped={skipped}, conflicts={conflicts}")
        return imported, skipped, conflicts

    def status(self) -> Optional[SyncManifest]:
        """获取远端同步状态

        Returns:
            远端清单，不存在返回 None
        """
        if not self.storage:
            return None

        manifest_data = self.storage.download(self._get_remote_path("manifest.json"))
        if not manifest_data:
            return None

        return SyncManifest.from_json(manifest_data.decode("utf-8"))


__all__ = [
    "SyncManifest",
    "MemoryRecord",
    "MemoryExporter",
    "MemoryImporter",
    "CloudSyncService",
]
