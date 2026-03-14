"""Fernet-based encrypted at-rest storage for Vaultrix.

Provides a simple API to encrypt/decrypt arbitrary bytes using a
locally-managed key.  The key is stored in ``~/.vaultrix/key`` with
restrictive permissions (0o600).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_DEFAULT_KEY_DIR = Path.home() / ".vaultrix"


class EncryptionManager:
    """Manage a Fernet key and provide encrypt / decrypt helpers."""

    def __init__(self, key_dir: Optional[Path] = None) -> None:
        self._key_dir = key_dir or _DEFAULT_KEY_DIR
        self._key_dir.mkdir(parents=True, exist_ok=True)
        self._key_path = self._key_dir / "key"
        self._fernet: Optional[Fernet] = None

    # -- key management ------------------------------------------------------

    def _load_or_generate_key(self) -> bytes:
        if self._key_path.exists():
            key = self._key_path.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            self._key_path.write_bytes(key)
            self._key_path.chmod(0o600)
            logger.info("Generated new encryption key at %s", self._key_path)
        return key

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._load_or_generate_key())
        return self._fernet

    # -- public API ----------------------------------------------------------

    def encrypt(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self.fernet.decrypt(token)

    def encrypt_json(self, obj: Any) -> bytes:
        raw = json.dumps(obj, default=str).encode("utf-8")
        return self.encrypt(raw)

    def decrypt_json(self, token: bytes) -> Any:
        raw = self.decrypt(token)
        return json.loads(raw)

    # -- file helpers --------------------------------------------------------

    def save_encrypted(self, path: Path, data: bytes) -> None:
        path.write_bytes(self.encrypt(data))

    def load_encrypted(self, path: Path) -> bytes:
        return self.decrypt(path.read_bytes())
