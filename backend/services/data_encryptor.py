"""
Data Encryptor - AES-256-GCM 加密服务

提供对称加密功能，用于保护云端存储的敏感记忆数据。

设计原则：
- 使用 AES-256-GCM（认证加密）
- 密钥仅存储在本地，永不上传
- 每次加密使用随机 nonce
- 支持流式加密（大文件）
"""

import logging
import os
import secrets
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# AES-256-GCM 参数
KEY_SIZE = 32  # 256 bits
NONCE_SIZE = 12  # 96 bits (recommended for GCM)
TAG_SIZE = 16  # 128 bits


class EncryptionError(Exception):
    """加密/解密错误"""
    pass


class DataEncryptor:
    """AES-256-GCM 数据加密器

    使用方式：
    1. 首次使用时调用 generate_key() 生成密钥
    2. 加密：encrypt(data) → 返回 nonce + ciphertext + tag
    3. 解密：decrypt(encrypted_data) → 返回原始数据

    密钥存储：
    - 密钥文件存储在本地（如 ~/.memory-anchor/encryption.key）
    - 首次初始化时提示用户备份密钥
    - 密钥丢失 = 数据丢失（无法恢复）
    """

    def __init__(self, key: Optional[bytes] = None, key_path: Optional[Path] = None):
        """初始化加密器

        Args:
            key: 直接提供 32 字节密钥
            key_path: 从文件加载密钥

        Raises:
            EncryptionError: 密钥无效或加载失败
        """
        # 延迟导入 cryptography（可选依赖）
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            self._aesgcm_class = AESGCM
        except ImportError as e:
            raise ImportError(
                "cryptography is required for encryption. "
                "Install with: uv add cryptography or pip install cryptography"
            ) from e

        self._key: Optional[bytes] = None
        self._aesgcm: Optional[object] = None

        if key:
            self._set_key(key)
        elif key_path:
            self._load_key(key_path)

    def _set_key(self, key: bytes) -> None:
        """设置加密密钥"""
        if len(key) != KEY_SIZE:
            raise EncryptionError(f"Invalid key size: expected {KEY_SIZE} bytes, got {len(key)}")

        self._key = key
        self._aesgcm = self._aesgcm_class(key)
        logger.debug("Encryption key set successfully")

    def _load_key(self, key_path: Path) -> None:
        """从文件加载密钥"""
        if not key_path.exists():
            raise EncryptionError(f"Key file not found: {key_path}")

        try:
            key = key_path.read_bytes()
            self._set_key(key)
            logger.info(f"Loaded encryption key from {key_path}")
        except Exception as e:
            raise EncryptionError(f"Failed to load key from {key_path}: {e}") from e

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化密钥"""
        return self._key is not None

    def encrypt(self, data: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """加密数据

        Args:
            data: 要加密的原始数据
            associated_data: 附加认证数据（AAD，可选）
                             AAD 不会被加密，但会被认证（防篡改）

        Returns:
            加密后的数据：nonce (12 bytes) + ciphertext + tag (16 bytes)

        Raises:
            EncryptionError: 加密失败
        """
        if not self.is_initialized:
            raise EncryptionError("Encryptor not initialized: no key set")

        try:
            # 生成随机 nonce
            nonce = secrets.token_bytes(NONCE_SIZE)

            # 加密（GCM 模式自动附加认证标签）
            ciphertext = self._aesgcm.encrypt(nonce, data, associated_data)

            # 返回 nonce + ciphertext（包含 tag）
            return nonce + ciphertext

        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted_data: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """解密数据

        Args:
            encrypted_data: 加密后的数据（nonce + ciphertext + tag）
            associated_data: 加密时使用的 AAD（必须完全匹配）

        Returns:
            解密后的原始数据

        Raises:
            EncryptionError: 解密失败（密钥错误、数据被篡改等）
        """
        if not self.is_initialized:
            raise EncryptionError("Encryptor not initialized: no key set")

        if len(encrypted_data) < NONCE_SIZE + TAG_SIZE:
            raise EncryptionError("Invalid encrypted data: too short")

        try:
            # 分离 nonce 和 ciphertext
            nonce = encrypted_data[:NONCE_SIZE]
            ciphertext = encrypted_data[NONCE_SIZE:]

            # 解密并验证
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, associated_data)
            return plaintext

        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e

    @staticmethod
    def generate_key() -> bytes:
        """生成新的加密密钥

        Returns:
            32 字节（256 位）随机密钥
        """
        return secrets.token_bytes(KEY_SIZE)

    @staticmethod
    def save_key(key: bytes, key_path: Path, overwrite: bool = False) -> None:
        """保存密钥到文件

        Args:
            key: 32 字节密钥
            key_path: 保存路径
            overwrite: 是否覆盖现有文件

        Raises:
            EncryptionError: 保存失败
        """
        if len(key) != KEY_SIZE:
            raise EncryptionError(f"Invalid key size: expected {KEY_SIZE} bytes")

        if key_path.exists() and not overwrite:
            raise EncryptionError(f"Key file already exists: {key_path}. Use overwrite=True to replace.")

        try:
            # 确保父目录存在
            key_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入密钥（设置安全权限）
            key_path.write_bytes(key)

            # 设置文件权限为 600（仅所有者可读写）
            os.chmod(key_path, 0o600)

            logger.info(f"Saved encryption key to {key_path}")

        except Exception as e:
            raise EncryptionError(f"Failed to save key to {key_path}: {e}") from e

    @classmethod
    def initialize_key(cls, key_path: Path, force: bool = False) -> "DataEncryptor":
        """初始化新密钥并创建加密器

        这是首次设置加密的便捷方法：
        1. 生成新密钥
        2. 保存到文件
        3. 返回初始化的加密器

        Args:
            key_path: 密钥保存路径
            force: 是否覆盖现有密钥

        Returns:
            初始化好的 DataEncryptor 实例
        """
        key = cls.generate_key()
        cls.save_key(key, key_path, overwrite=force)
        return cls(key=key)


def encrypt_file(input_path: Path, output_path: Path, encryptor: DataEncryptor) -> None:
    """加密文件

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        encryptor: 加密器实例
    """
    data = input_path.read_bytes()
    encrypted = encryptor.encrypt(data)
    output_path.write_bytes(encrypted)
    logger.debug(f"Encrypted {input_path} -> {output_path} ({len(data)} -> {len(encrypted)} bytes)")


def decrypt_file(input_path: Path, output_path: Path, encryptor: DataEncryptor) -> None:
    """解密文件

    Args:
        input_path: 加密文件路径
        output_path: 输出文件路径
        encryptor: 加密器实例
    """
    encrypted = input_path.read_bytes()
    data = encryptor.decrypt(encrypted)
    output_path.write_bytes(data)
    logger.debug(f"Decrypted {input_path} -> {output_path} ({len(encrypted)} -> {len(data)} bytes)")


__all__ = [
    "DataEncryptor",
    "EncryptionError",
    "encrypt_file",
    "decrypt_file",
    "KEY_SIZE",
    "NONCE_SIZE",
    "TAG_SIZE",
]
