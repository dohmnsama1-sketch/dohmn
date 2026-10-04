"""Small .env reader; values are configuration, never executable shell code."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, value = line.partition("=")
        if not sep or not key.strip().isidentifier():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def public_origin(default: str = "http://127.0.0.1:8000") -> str:
    origin = os.getenv("MENDCART_PUBLIC_URL", default).rstrip("/")
    parsed = urlsplit(origin)
    if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("MENDCART_PUBLIC_URL must be an origin without credentials, a path, or query.")
    if not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise ValueError("MENDCART_PUBLIC_URL must be a valid HTTP(S) origin.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Public return URLs require HTTPS; HTTP is allowed only for localhost.")
    return origin
