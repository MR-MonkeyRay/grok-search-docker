from __future__ import annotations

import re
from typing import Any


_THINK_PATTERN = re.compile(r"<\/think>|\<think", re.IGNORECASE)
_FULL_BLOCK_PATTERN = re.compile(r"<think[^>]*>.*?<\/think>", re.DOTALL | re.IGNORECASE)


def strip_think_segments(text: str) -> str:
    if not isinstance(text, str):
        return text

    if _THINK_PATTERN.search(text) is None:
        return text

    text = _FULL_BLOCK_PATTERN.sub("", text)

    think_pos = text.lower().find("<think")
    if think_pos != -1:
        text = text[:think_pos]

    text = text.replace("</think>", "")

    return text


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_think_segments(value)
    if isinstance(value, dict):
        return {k: sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)

    if isinstance(value, (str, dict, list, tuple)):
        return value

    if not hasattr(value, "__dict__"):
        return value

    target_fields = ("text", "content", "structured_content", "data")
    updates = {}

    for field in target_fields:
        if hasattr(value, field):
            raw = getattr(value, field)
            sanitized = sanitize_value(raw)
            updates[field] = sanitized

    if not updates:
        return value

    try:
        if hasattr(value, "model_copy"):
            return value.model_copy(update=updates)
    except Exception:
        pass

    try:
        import copy
        new_obj = copy.copy(value)
        for k, v in updates.items():
            setattr(new_obj, k, v)
        return new_obj
    except Exception:
        pass

    try:
        new_obj = object.__new__(type(value))
        new_obj.__dict__.update(value.__dict__)
        for k, v in updates.items():
            setattr(new_obj, k, v)
        return new_obj
    except Exception:
        pass

    return value


def should_sanitize_tool(tool_name: str) -> bool:
    return tool_name == "web_search"
