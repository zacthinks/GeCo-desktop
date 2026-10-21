"""Small JSON-lines protocol between the installed app and its runner."""

from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1


class ProtocolError(ValueError):
    """A backend response is malformed or incompatible."""


def request(action: str, **arguments: Any) -> dict[str, Any]:
    if not action or not isinstance(action, str):
        raise ProtocolError("action must be a non-empty string")
    return {"version": PROTOCOL_VERSION, "action": action, "arguments": arguments}


def encode(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n"


def decode(line: str) -> dict[str, Any]:
    try:
        value = json.loads(line)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Invalid JSON response") from exc
    if not isinstance(value, dict) or value.get("version") != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol message or version")
    return value
