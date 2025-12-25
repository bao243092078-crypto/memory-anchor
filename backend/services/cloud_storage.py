"""
Cloud Storage Backend - 云端存储后端抽象

支持多种云存储提供商：
- S3 (AWS)
- R2 (Cloudflare)
- MinIO (Self-hosted)

设计原则：
- Protocol 模式，允许第三方实现
- 最小化 API 依赖
- 重试和错误处理内置
"""

import logging
from abc import abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class CloudObject:
    """云端对象元数据"""
    key: str
    size: int
    last_modified: str
    etag: Optional[str] = None
    content_type: Optional[str] = None


@runtime_checkable
class CloudStorageBackend(Protocol):
    """云端存储后端协议

    所有云存储提供商必须实现此接口。
    使用 Protocol 而非 ABC，允许结构化子类型（duck typing with type hints）。
    """

    @abstractmethod
    def upload(self, key: str, data: bytes | BinaryIO, content_type: str = "application/octet-stream") -> bool:
        """上传数据到云端

        Args:
            key: 对象键（路径）
            data: 数据内容（bytes 或 file-like object）
            content_type: MIME 类型

        Returns:
            是否成功
        """
        ...

    @abstractmethod
    def download(self, key: str) -> Optional[bytes]:
        """从云端下载数据

        Args:
            key: 对象键（路径）

        Returns:
            数据内容，不存在返回 None
        """
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查对象是否存在

        Args:
            key: 对象键（路径）

        Returns:
            是否存在
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除云端对象

        Args:
            key: 对象键（路径）

        Returns:
            是否成功
        """
        ...

    @abstractmethod
    def list_objects(self, prefix: str = "") -> list[CloudObject]:
        """列出对象

        Args:
            prefix: 路径前缀

        Returns:
            对象列表
        """
        ...

    @abstractmethod
    def get_metadata(self, key: str) -> Optional[CloudObject]:
        """获取对象元数据

        Args:
            key: 对象键（路径）

        Returns:
            元数据，不存在返回 None
        """
        ...


class S3Backend:
    """AWS S3 / S3-Compatible 存储后端

    支持：
    - AWS S3
    - Cloudflare R2
    - MinIO
    - 其他 S3 兼容存储
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        prefix: str = "",
    ):
        """初始化 S3 后端

        Args:
            bucket: S3 桶名
            region: AWS 区域
            endpoint_url: 自定义端点（MinIO/R2）
            access_key_id: AWS Access Key ID（优先使用环境变量）
            secret_access_key: AWS Secret Access Key（优先使用环境变量）
            prefix: 存储路径前缀
        """
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.prefix = prefix.strip("/")

        # 延迟导入 boto3（可选依赖）
        try:
            import boto3
            from botocore.config import Config
        except ImportError as e:
            raise ImportError(
                "boto3 is required for cloud sync. "
                "Install with: uv add boto3 or pip install boto3"
            ) from e

        # 创建 S3 客户端
        config = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=10,
            read_timeout=30,
        )

        client_kwargs = {
            "region_name": region,
            "config": config,
        }

        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key

        self._client = boto3.client("s3", **client_kwargs)
        logger.info(f"S3Backend initialized: bucket={bucket}, region={region}, endpoint={endpoint_url}")

    def _full_key(self, key: str) -> str:
        """获取完整的对象键（包含前缀）"""
        if self.prefix:
            return f"{self.prefix}/{key.lstrip('/')}"
        return key.lstrip("/")

    def upload(self, key: str, data: bytes | BinaryIO, content_type: str = "application/octet-stream") -> bool:
        """上传数据到 S3"""
        full_key = self._full_key(key)

        try:
            if isinstance(data, bytes):
                body = BytesIO(data)
            else:
                body = data

            self._client.put_object(
                Bucket=self.bucket,
                Key=full_key,
                Body=body,
                ContentType=content_type,
            )
            logger.debug(f"Uploaded: s3://{self.bucket}/{full_key}")
            return True
        except Exception as e:
            logger.error(f"Upload failed for {full_key}: {e}")
            return False

    def download(self, key: str) -> Optional[bytes]:
        """从 S3 下载数据"""
        full_key = self._full_key(key)

        try:
            response = self._client.get_object(Bucket=self.bucket, Key=full_key)
            data = response["Body"].read()
            logger.debug(f"Downloaded: s3://{self.bucket}/{full_key} ({len(data)} bytes)")
            return data
        except self._client.exceptions.NoSuchKey:
            logger.debug(f"Object not found: s3://{self.bucket}/{full_key}")
            return None
        except Exception as e:
            logger.error(f"Download failed for {full_key}: {e}")
            return None

    def exists(self, key: str) -> bool:
        """检查对象是否存在"""
        full_key = self._full_key(key)

        try:
            self._client.head_object(Bucket=self.bucket, Key=full_key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """删除对象"""
        full_key = self._full_key(key)

        try:
            self._client.delete_object(Bucket=self.bucket, Key=full_key)
            logger.debug(f"Deleted: s3://{self.bucket}/{full_key}")
            return True
        except Exception as e:
            logger.error(f"Delete failed for {full_key}: {e}")
            return False

    def list_objects(self, prefix: str = "") -> list[CloudObject]:
        """列出对象"""
        full_prefix = self._full_key(prefix) if prefix else self.prefix

        try:
            objects = []
            paginator = self._client.get_paginator("list_objects_v2")

            for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    # 移除前缀
                    key = obj["Key"]
                    if self.prefix and key.startswith(self.prefix + "/"):
                        key = key[len(self.prefix) + 1:]

                    objects.append(CloudObject(
                        key=key,
                        size=obj["Size"],
                        last_modified=obj["LastModified"].isoformat(),
                        etag=obj.get("ETag", "").strip('"'),
                    ))

            logger.debug(f"Listed {len(objects)} objects with prefix '{full_prefix}'")
            return objects
        except Exception as e:
            logger.error(f"List objects failed: {e}")
            return []

    def get_metadata(self, key: str) -> Optional[CloudObject]:
        """获取对象元数据"""
        full_key = self._full_key(key)

        try:
            response = self._client.head_object(Bucket=self.bucket, Key=full_key)
            return CloudObject(
                key=key,
                size=response["ContentLength"],
                last_modified=response["LastModified"].isoformat(),
                etag=response.get("ETag", "").strip('"'),
                content_type=response.get("ContentType"),
            )
        except Exception:
            return None


def create_storage_backend(
    provider: str,
    bucket: str,
    region: str = "us-east-1",
    endpoint_url: Optional[str] = None,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    prefix: str = "",
) -> CloudStorageBackend:
    """创建存储后端

    Args:
        provider: 提供商类型 (s3 | r2 | minio)
        bucket: 桶名
        region: 区域
        endpoint_url: 自定义端点
        access_key_id: Access Key ID
        secret_access_key: Secret Access Key
        prefix: 存储路径前缀

    Returns:
        存储后端实例
    """
    if provider == "r2":
        # Cloudflare R2 使用 S3 兼容 API
        if not endpoint_url:
            raise ValueError("R2 requires endpoint_url (e.g., https://<account_id>.r2.cloudflarestorage.com)")
        region = "auto"  # R2 使用 auto 区域

    elif provider == "minio":
        if not endpoint_url:
            endpoint_url = "http://localhost:9000"

    return S3Backend(
        bucket=bucket,
        region=region,
        endpoint_url=endpoint_url,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        prefix=prefix,
    )


__all__ = [
    "CloudStorageBackend",
    "CloudObject",
    "S3Backend",
    "create_storage_backend",
]
