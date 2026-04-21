"""
API Key Encryption Utilities

AES-256 encryption for storing API keys securely in database.
Uses Fernet symmetric encryption from cryptography library.

References:
- Requirements: R7 (Security)
- Design: model-config-management/design.md
"""
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class KeyEncryption:
    """
    AES-256 encryption for API keys using Fernet.

    The encryption key should be stored in environment variable:
    MODEL_CONFIG_ENCRYPTION_KEY

    To generate a new key:
        from cryptography.fernet import Fernet
        Fernet.generate_key().decode()
    """

    def __init__(self, encryption_key: str | None = None):
        """
        Initialize encryption with key from env or parameter.

        Args:
            encryption_key: Optional encryption key. If not provided,
                           reads from MODEL_CONFIG_ENCRYPTION_KEY env var.
        """
        key = encryption_key or os.getenv("MODEL_CONFIG_ENCRYPTION_KEY")

        if not key:
            logger.error(
                "MODEL_CONFIG_ENCRYPTION_KEY not set. "
                "Model configuration encryption is unavailable."
            )
            raise ValueError("MODEL_CONFIG_ENCRYPTION_KEY is required")

        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, RuntimeError) as e:
            logger.error(f"Invalid encryption key: {e}")
            raise ValueError("Invalid encryption key format") from e

    def encrypt(self, plain_text: str) -> Result[str]:
        """
        Encrypt a plain text string.

        Args:
            plain_text: The string to encrypt (e.g., API key)

        Returns:
            Result with encrypted string or error
        """
        if not plain_text:
            return Result.fail("[ENCRYPTION_ERROR] Empty input")

        try:
            encrypted = self._fernet.encrypt(plain_text.encode())
            return Result.ok(encrypted.decode())
        except (ValueError, RuntimeError) as e:
            logger.error(f"Encryption failed: {e}")
            return Result.fail(f"[ENCRYPTION_ERROR] {str(e)}")

    def decrypt(self, encrypted_text: str) -> Result[str]:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_text: The encrypted string

        Returns:
            Result with decrypted string or error
        """
        if not encrypted_text:
            return Result.fail("[DECRYPTION_ERROR] Empty input")

        try:
            decrypted = self._fernet.decrypt(encrypted_text.encode())
            return Result.ok(decrypted.decode())
        except InvalidToken:
            logger.error("Decryption failed: Invalid token")
            return Result.fail("[DECRYPTION_ERROR] Invalid token or key")
        except (ValueError, RuntimeError) as e:
            logger.error(f"Decryption failed: {e}")
            return Result.fail(f"[DECRYPTION_ERROR] {str(e)}")

    @staticmethod
    def mask_key(key: str) -> str:
        """
        Mask API key for display in UI.

        Examples:
            "sk-abc123xyz789" -> "sk-...9789"
            "short" -> "****"

        Args:
            key: The API key to mask

        Returns:
            Masked string showing only prefix and last 4 chars
        """
        if not key:
            return "****"

        if len(key) <= 8:
            return "****"

        # Show first 3 chars and last 4 chars
        return f"{key[:3]}...{key[-4:]}"

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key string
        """
        return Fernet.generate_key().decode()


# Singleton instance
_encryption: KeyEncryption | None = None


@lru_cache(maxsize=1)
def get_encryption() -> KeyEncryption:
    """
    Get singleton KeyEncryption instance.

    Returns:
        KeyEncryption instance
    """
    global _encryption
    if _encryption is None:
        _encryption = KeyEncryption()
    return _encryption


def encrypt_api_key(plain_key: str) -> Result[str]:
    """
    Convenience function to encrypt an API key.

    Args:
        plain_key: Plain text API key

    Returns:
        Result with encrypted key or error
    """
    try:
        return get_encryption().encrypt(plain_key)
    except ValueError as e:
        logger.error(f"Encryption unavailable: {e}")
        return Result.fail("[ENCRYPTION_ERROR] Encryption key not configured")


def decrypt_api_key(encrypted_key: str) -> Result[str]:
    """
    Convenience function to decrypt an API key.

    Args:
        encrypted_key: Encrypted API key

    Returns:
        Result with decrypted key or error
    """
    try:
        return get_encryption().decrypt(encrypted_key)
    except ValueError as e:
        logger.error(f"Decryption unavailable: {e}")
        return Result.fail("[DECRYPTION_ERROR] Encryption key not configured")


def mask_api_key(key: str) -> str:
    """
    Convenience function to mask an API key for display.

    Args:
        key: API key to mask

    Returns:
        Masked string
    """
    return KeyEncryption.mask_key(key)
