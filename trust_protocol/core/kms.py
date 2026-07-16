"""KMS -- envelope encryption (wrap / unwrap / generate data keys).

Complements the credential vault. The vault's proxy is *use-but-never-see*: for API keys the
agent should never touch, the server injects them into outbound calls. The KMS is the opposite
need: keys the caller **must** use itself (encryption-at-rest for silos, backups, local DBs,
per-field secrets). The caller holds only a **wrapped** blob at rest and unwraps on demand; the
KMS master key is derived from the unsealed vault password and never leaves the server process.

Master key = HKDF-Expand(PBKDF2-HMAC-SHA256(vault_password, vault_salt), info="trust-protocol-kms-v1").
Deriving from the same secret keeps unlock unified with the vault, while the distinct HKDF info gives
domain separation from the credential-encryption key. Wrapped blob = version(1) | nonce(12) |
AES-256-GCM ciphertext+tag, optionally bound to caller-supplied AAD.
"""
from __future__ import annotations

import os
from typing import Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_WRAP_VERSION = 1
_KMS_INFO = b"trust-protocol-kms-v1"
_PBKDF2_ITERS = 200_000


def _master_key(password: str, salt: bytes) -> bytes:
    prk = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_PBKDF2_ITERS).derive(
        password.encode()
    )
    return HKDFExpand(algorithm=hashes.SHA256(), length=32, info=_KMS_INFO).derive(prk)


class KMS:
    """Envelope encryption under a master key derived from the vault password."""

    def __init__(self, password: str, salt: bytes) -> None:
        self._key = _master_key(password, salt)

    def wrap(self, plaintext: bytes, aad: bytes = b"") -> bytes:
        nonce = os.urandom(12)
        ct = AESGCM(self._key).encrypt(nonce, plaintext, aad or None)
        return bytes([_WRAP_VERSION]) + nonce + ct

    def unwrap(self, blob: bytes, aad: bytes = b"") -> bytes:
        if not blob or blob[0] != _WRAP_VERSION:
            raise ValueError("unsupported wrap version")
        nonce, ct = blob[1:13], blob[13:]
        return AESGCM(self._key).decrypt(nonce, ct, aad or None)

    def generate_data_key(self, nbytes: int = 32, aad: bytes = b"") -> Tuple[bytes, bytes]:
        """Return (plaintext_key, wrapped_key). Caller uses the plaintext then discards it, keeping
        only the wrapped blob at rest (KMS GenerateDataKey pattern)."""
        dk = os.urandom(nbytes)
        return dk, self.wrap(dk, aad)
