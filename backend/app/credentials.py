"""Protect integration secrets with Windows user-bound data protection."""

import base64
import sys


PREFIX = "dpapi:"


def protect(value: str) -> str:
    if not value or value.startswith(PREFIX) or sys.platform != "win32":
        return value
    import win32crypt

    encrypted = win32crypt.CryptProtectData(value.encode(), "AgentDesk", None, None, None, 1)
    return PREFIX + base64.b64encode(encrypted).decode("ascii")


def reveal(value: str) -> str:
    if not value.startswith(PREFIX):
        return value
    if sys.platform != "win32":
        raise ValueError("These credentials belong to a Windows user account.")
    import win32crypt

    return win32crypt.CryptUnprotectData(base64.b64decode(value[len(PREFIX):]), None, None, None, 1)[1].decode()
