"""Cryptographic skill signing and verification for VaultHub.

Provides HMAC-SHA256 based signing of skill directories so that
skills can be authenticated before execution.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SIGNATURE_FILENAME = "SIGNATURE.json"
SIGNABLE_EXTENSIONS = {".py", ".yaml", ".yml"}


class KeyPair(BaseModel):
    """A signing keypair stored on disk."""

    public_key: str  # hex-encoded
    private_key: str  # hex-encoded
    key_id: str  # first 8 chars of SHA-256(public_key)
    created_at: str


class SkillSignature(BaseModel):
    """A cryptographic signature attached to a skill directory."""

    skill_name: str
    skill_version: str
    content_hash: str  # SHA-256 of skill directory contents
    signature: str  # hex-encoded HMAC-SHA256
    signer_key_id: str
    signed_at: str
    algorithm: str = "hmac-sha256"


def _derive_key_id(public_key_hex: str) -> str:
    """Derive a short key ID from the public key."""
    return hashlib.sha256(public_key_hex.encode()).hexdigest()[:8]


class SigningManager:
    """Manages keypair generation, skill signing, and verification."""

    def __init__(self, key_dir: Optional[Path] = None) -> None:
        self.key_dir = key_dir or Path.home() / ".vaultrix" / "keys"
        self.key_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def generate_keypair(self) -> KeyPair:
        """Generate a new random keypair and persist it to *key_dir*."""
        public_key_hex = os.urandom(32).hex()
        private_key_hex = os.urandom(32).hex()
        key_id = _derive_key_id(public_key_hex)
        now = datetime.now(timezone.utc).isoformat()

        keypair = KeyPair(
            public_key=public_key_hex,
            private_key=private_key_hex,
            key_id=key_id,
            created_at=now,
        )

        key_file = self.key_dir / f"{key_id}.json"
        key_file.write_text(keypair.model_dump_json(indent=2))
        # Restrict permissions so only the owner can read the private key.
        key_file.chmod(0o600)

        logger.info("Generated keypair %s", key_id)
        return keypair

    def load_keypair(self, key_id: Optional[str] = None) -> KeyPair:
        """Load a keypair by *key_id*, or the first one found."""
        if key_id:
            key_file = self.key_dir / f"{key_id}.json"
            if not key_file.exists():
                raise FileNotFoundError(f"No keypair found for key_id={key_id}")
            return KeyPair.model_validate_json(key_file.read_text())

        # Fall back to the first key file found (sorted for determinism).
        key_files = sorted(self.key_dir.glob("*.json"))
        if not key_files:
            raise FileNotFoundError(
                "No keypairs found. Run generate_keypair() first."
            )
        return KeyPair.model_validate_json(key_files[0].read_text())

    def list_keys(self) -> List[KeyPair]:
        """Return all stored keypairs."""
        keys: List[KeyPair] = []
        for kf in sorted(self.key_dir.glob("*.json")):
            try:
                keys.append(KeyPair.model_validate_json(kf.read_text()))
            except Exception:
                logger.warning("Skipping invalid key file: %s", kf)
        return keys

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_skill(skill_dir: Path) -> str:
        """Compute a deterministic SHA-256 hash of all signable files.

        Only ``.py`` and ``.yaml``/``.yml`` files are included.
        Files are sorted by name so the hash is reproducible.
        The signature file itself is excluded from the hash.
        """
        h = hashlib.sha256()
        files = sorted(
            p
            for p in skill_dir.iterdir()
            if p.is_file()
            and p.suffix in SIGNABLE_EXTENSIONS
            and p.name != SIGNATURE_FILENAME
        )
        if not files:
            raise ValueError(
                f"No signable files (.py, .yaml) found in {skill_dir}"
            )
        for fp in files:
            # Include the filename in the hash so renames are detected.
            h.update(fp.name.encode())
            h.update(fp.read_bytes())
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Signing & verification
    # ------------------------------------------------------------------

    def sign_skill(
        self,
        skill_dir: Path,
        key: Optional[KeyPair] = None,
    ) -> SkillSignature:
        """Sign a skill directory and write ``SIGNATURE.json``."""
        skill_dir = Path(skill_dir)
        if not skill_dir.is_dir():
            raise NotADirectoryError(f"{skill_dir} is not a directory")

        if key is None:
            key = self.load_keypair()

        content_hash = self.hash_skill(skill_dir)

        # Derive skill metadata from a manifest if present, else from dir name.
        skill_name, skill_version = self._read_skill_meta(skill_dir)

        now = datetime.now(timezone.utc).isoformat()

        # HMAC-SHA256 with the private key as the HMAC secret.
        mac = hmac.new(
            bytes.fromhex(key.private_key),
            content_hash.encode(),
            hashlib.sha256,
        )
        signature_hex = mac.hexdigest()

        sig = SkillSignature(
            skill_name=skill_name,
            skill_version=skill_version,
            content_hash=content_hash,
            signature=signature_hex,
            signer_key_id=key.key_id,
            signed_at=now,
        )

        sig_path = skill_dir / SIGNATURE_FILENAME
        sig_path.write_text(json.dumps(sig.model_dump(), indent=2))
        logger.info(
            "Signed skill '%s' v%s (key %s)",
            skill_name,
            skill_version,
            key.key_id,
        )
        return sig

    def verify_skill(self, skill_dir: Path) -> bool:
        """Verify the signature of a skill directory.

        Returns ``True`` when the SIGNATURE.json is present and the
        HMAC matches the current content hash.  Returns ``False`` otherwise.
        """
        skill_dir = Path(skill_dir)
        sig_path = skill_dir / SIGNATURE_FILENAME
        if not sig_path.exists():
            logger.warning("No SIGNATURE.json found in %s", skill_dir)
            return False

        try:
            sig = SkillSignature.model_validate_json(sig_path.read_text())
        except Exception:
            logger.error("Invalid SIGNATURE.json in %s", skill_dir)
            return False

        # Re-compute content hash.
        try:
            current_hash = self.hash_skill(skill_dir)
        except ValueError:
            logger.error("No signable files in %s", skill_dir)
            return False

        if current_hash != sig.content_hash:
            logger.warning(
                "Content hash mismatch for skill '%s' — files may have been tampered with",
                sig.skill_name,
            )
            return False

        # Load the signer's keypair so we can re-derive the HMAC.
        try:
            signer_key = self.load_keypair(sig.signer_key_id)
        except FileNotFoundError:
            logger.error(
                "Signer key %s not found — cannot verify", sig.signer_key_id
            )
            return False

        expected_mac = hmac.new(
            bytes.fromhex(signer_key.private_key),
            current_hash.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_mac, sig.signature):
            logger.warning("Signature verification failed for '%s'", sig.skill_name)
            return False

        logger.info("Signature verified for '%s' v%s", sig.skill_name, sig.skill_version)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_skill_meta(skill_dir: Path) -> tuple[str, str]:
        """Extract skill name and version from skill.yaml if present."""
        manifest = skill_dir / "skill.yaml"
        if manifest.exists():
            # Lightweight YAML parsing — avoids pulling in PyYAML just for two fields.
            name = skill_dir.name
            version = "0.0.0"
            for line in manifest.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("name:"):
                    name = stripped.split(":", 1)[1].strip().strip("'\"")
                elif stripped.startswith("version:"):
                    version = stripped.split(":", 1)[1].strip().strip("'\"")
            return name, version
        return skill_dir.name, "0.0.0"
