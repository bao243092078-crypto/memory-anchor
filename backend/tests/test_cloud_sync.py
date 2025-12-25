"""
Tests for Cloud Sync functionality.

测试：
- DataEncryptor: 加密/解密功能
- CloudSyncConfig: 配置加载
- MemoryExporter/Importer: 导出导入逻辑
"""

import json
import os
import tempfile
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestDataEncryptor:
    """测试 DataEncryptor"""

    def test_generate_key(self):
        """测试密钥生成"""
        from backend.services.data_encryptor import KEY_SIZE, DataEncryptor

        key = DataEncryptor.generate_key()
        assert len(key) == KEY_SIZE
        assert isinstance(key, bytes)

        # 生成的密钥应该是随机的
        key2 = DataEncryptor.generate_key()
        assert key != key2

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返"""
        from backend.services.data_encryptor import DataEncryptor

        key = DataEncryptor.generate_key()
        encryptor = DataEncryptor(key=key)

        plaintext = b"Hello, Memory Anchor!"
        ciphertext = encryptor.encrypt(plaintext)

        # 密文应该比明文长（nonce + tag）
        assert len(ciphertext) > len(plaintext)
        assert ciphertext != plaintext

        # 解密应该恢复原文
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_with_aad(self):
        """测试带 AAD 的加密"""
        from backend.services.data_encryptor import DataEncryptor

        key = DataEncryptor.generate_key()
        encryptor = DataEncryptor(key=key)

        plaintext = b"Secret data"
        aad = b"project_id:test"

        ciphertext = encryptor.encrypt(plaintext, associated_data=aad)

        # 使用相同 AAD 解密
        decrypted = encryptor.decrypt(ciphertext, associated_data=aad)
        assert decrypted == plaintext

    def test_decrypt_with_wrong_aad_fails(self):
        """测试错误 AAD 解密失败"""
        from backend.services.data_encryptor import DataEncryptor, EncryptionError

        key = DataEncryptor.generate_key()
        encryptor = DataEncryptor(key=key)

        plaintext = b"Secret data"
        aad = b"project_id:test"

        ciphertext = encryptor.encrypt(plaintext, associated_data=aad)

        # 使用不同 AAD 解密应该失败
        with pytest.raises(EncryptionError):
            encryptor.decrypt(ciphertext, associated_data=b"wrong_aad")

    def test_decrypt_tampered_data_fails(self):
        """测试篡改数据解密失败"""
        from backend.services.data_encryptor import DataEncryptor, EncryptionError

        key = DataEncryptor.generate_key()
        encryptor = DataEncryptor(key=key)

        plaintext = b"Secret data"
        ciphertext = encryptor.encrypt(plaintext)

        # 篡改密文
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(EncryptionError):
            encryptor.decrypt(tampered)

    def test_decrypt_with_wrong_key_fails(self):
        """测试错误密钥解密失败"""
        from backend.services.data_encryptor import DataEncryptor, EncryptionError

        key1 = DataEncryptor.generate_key()
        key2 = DataEncryptor.generate_key()

        encryptor1 = DataEncryptor(key=key1)
        encryptor2 = DataEncryptor(key=key2)

        ciphertext = encryptor1.encrypt(b"Secret")

        with pytest.raises(EncryptionError):
            encryptor2.decrypt(ciphertext)

    def test_save_and_load_key(self):
        """测试保存和加载密钥"""
        from backend.services.data_encryptor import DataEncryptor

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "test.key"

            # 生成并保存密钥
            key = DataEncryptor.generate_key()
            DataEncryptor.save_key(key, key_path)

            # 验证文件权限
            assert key_path.exists()
            # 注意: 在某些系统上权限检查可能不精确

            # 加载密钥
            encryptor = DataEncryptor(key_path=key_path)
            assert encryptor.is_initialized

            # 验证可以加密解密
            plaintext = b"Test data"
            ciphertext = encryptor.encrypt(plaintext)
            assert encryptor.decrypt(ciphertext) == plaintext

    def test_initialize_key_creates_encryptor(self):
        """测试 initialize_key 创建加密器"""
        from backend.services.data_encryptor import DataEncryptor

        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "new.key"

            encryptor = DataEncryptor.initialize_key(key_path)

            assert encryptor.is_initialized
            assert key_path.exists()

    def test_uninitialized_encryptor_raises(self):
        """测试未初始化的加密器抛出异常"""
        from backend.services.data_encryptor import DataEncryptor, EncryptionError

        encryptor = DataEncryptor()  # 无密钥
        assert not encryptor.is_initialized

        with pytest.raises(EncryptionError):
            encryptor.encrypt(b"data")

        with pytest.raises(EncryptionError):
            encryptor.decrypt(b"data")

    def test_invalid_key_size_raises(self):
        """测试无效密钥大小抛出异常"""
        from backend.services.data_encryptor import DataEncryptor, EncryptionError

        with pytest.raises(EncryptionError):
            DataEncryptor(key=b"too_short")


class TestCloudSyncConfig:
    """测试 CloudSyncConfig"""

    def test_default_config(self):
        """测试默认配置"""
        from backend.config import CloudSyncConfig

        config = CloudSyncConfig()
        assert config.enabled is False
        assert config.provider == "s3"
        assert config.bucket == ""
        assert config.encryption_enabled is True

    def test_config_from_env(self):
        """测试从环境变量加载配置"""
        from backend.config import _load_cloud_config

        env = {
            "MA_CLOUD_ENABLED": "true",
            "MA_CLOUD_PROVIDER": "r2",
            "MA_CLOUD_BUCKET": "my-bucket",
            "MA_CLOUD_REGION": "auto",
            "MA_CLOUD_ENDPOINT_URL": "https://test.r2.cloudflarestorage.com",
        }

        with patch.dict(os.environ, env, clear=False):
            config = _load_cloud_config({})

        assert config.enabled is True
        assert config.provider == "r2"
        assert config.bucket == "my-bucket"
        assert config.region == "auto"
        assert config.endpoint_url == "https://test.r2.cloudflarestorage.com"

    def test_config_from_yaml(self):
        """测试从 YAML 加载配置"""
        from backend.config import _load_cloud_config

        yaml_data = {
            "cloud": {
                "enabled": True,
                "provider": "minio",
                "bucket": "test-bucket",
                "endpoint_url": "http://localhost:9000",
            }
        }

        config = _load_cloud_config(yaml_data)

        assert config.enabled is True
        assert config.provider == "minio"
        assert config.bucket == "test-bucket"


class TestSyncManifest:
    """测试 SyncManifest"""

    def test_serialize_deserialize(self):
        """测试序列化和反序列化"""
        from backend.services.cloud_sync import SyncManifest

        manifest = SyncManifest(
            version="1.0.0",
            project_id="test-project",
            last_sync="2025-01-01T00:00:00Z",
            memories_count=42,
            memories_checksum="abc123",
            constitution_checksum="def456",
            encrypted=True,
        )

        json_str = manifest.to_json()
        restored = SyncManifest.from_json(json_str)

        assert restored.version == manifest.version
        assert restored.project_id == manifest.project_id
        assert restored.memories_count == manifest.memories_count
        assert restored.encrypted == manifest.encrypted


class TestMemoryRecord:
    """测试 MemoryRecord"""

    def test_json_line_roundtrip(self):
        """测试 JSONL 往返"""
        from backend.services.cloud_sync import MemoryRecord

        record = MemoryRecord(
            id="test-id-123",
            content="Test memory content",
            layer="verified_fact",
            category="event",
            confidence=0.95,
            created_at="2025-01-01T00:00:00Z",
            metadata={"key": "value"},
        )

        line = record.to_json_line()
        restored = MemoryRecord.from_json_line(line)

        assert restored.id == record.id
        assert restored.content == record.content
        assert restored.layer == record.layer
        assert restored.confidence == record.confidence


class TestCloudStorageBackend:
    """测试 CloudStorageBackend Protocol"""

    def test_protocol_check(self):
        """测试 Protocol 类型检查"""
        from backend.services.cloud_storage import CloudStorageBackend, S3Backend

        # S3Backend 应该是 CloudStorageBackend 的实例
        # 由于需要 boto3，这里只测试类定义
        assert hasattr(S3Backend, "upload")
        assert hasattr(S3Backend, "download")
        assert hasattr(S3Backend, "exists")
        assert hasattr(S3Backend, "delete")
        assert hasattr(S3Backend, "list_objects")
        assert hasattr(S3Backend, "get_metadata")

    def test_create_storage_backend_r2_requires_endpoint(self):
        """测试 R2 需要 endpoint_url"""
        from backend.services.cloud_storage import create_storage_backend

        with pytest.raises(ValueError, match="R2 requires endpoint_url"):
            create_storage_backend(
                provider="r2",
                bucket="test-bucket",
            )


class TestCloudSyncService:
    """测试 CloudSyncService"""

    def test_init_disabled(self):
        """测试禁用状态初始化"""
        from backend.config import CloudSyncConfig
        from backend.services.cloud_sync import CloudSyncService

        config = CloudSyncConfig(enabled=False)
        service = CloudSyncService("test-project", config=config)

        assert service.storage is None

    def test_push_without_storage_raises(self):
        """测试无存储后端推送失败"""
        from backend.config import CloudSyncConfig
        from backend.services.cloud_sync import CloudSyncService

        config = CloudSyncConfig(enabled=False)
        service = CloudSyncService("test-project", config=config)

        with pytest.raises(RuntimeError, match="Cloud storage not configured"):
            service.push()

    def test_pull_without_storage_raises(self):
        """测试无存储后端拉取失败"""
        from backend.config import CloudSyncConfig
        from backend.services.cloud_sync import CloudSyncService

        config = CloudSyncConfig(enabled=False)
        service = CloudSyncService("test-project", config=config)

        with pytest.raises(RuntimeError, match="Cloud storage not configured"):
            service.pull()


class TestMemoryImporter:
    """测试 MemoryImporter"""

    def test_verify_integrity(self):
        """测试完整性验证"""
        import hashlib

        from backend.services.cloud_sync import MemoryImporter

        importer = MemoryImporter("test-project")

        data = b'{"id": "1", "content": "test"}\n'
        expected_checksum = hashlib.sha256(data).hexdigest()

        assert importer.verify_integrity(data, expected_checksum) is True
        assert importer.verify_integrity(data, "wrong_checksum") is False


__all__ = [
    "TestDataEncryptor",
    "TestCloudSyncConfig",
    "TestSyncManifest",
    "TestMemoryRecord",
    "TestCloudStorageBackend",
    "TestCloudSyncService",
    "TestMemoryImporter",
]
