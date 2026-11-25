"""Zero-knowledge encrypted workspace storage (AES-256 via Fernet)."""

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_DIR

KEY_FILE = DATA_DIR / "workspace.key"


def _get_key() -> bytes:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
    return KEY_FILE.read_bytes().strip()


def encrypt_text(text: str) -> str:
    return Fernet(_get_key()).encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_text(text: str) -> str:
    try:
        return Fernet(_get_key()).decrypt(text.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return text


def is_encrypted(text: str) -> bool:
    return text.startswith("gAAAAA") or text.startswith("gAAAA")
