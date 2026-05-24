"""SSE 帮助函数，沿用 routers/copywrites.py 已验证的格式。"""
import json
from typing import Any


def sse_event(event: str, data: Any) -> str:
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False)
    elif not isinstance(data, str):
        data = str(data)
    return f"event: {event}\ndata: {data}\n\n"
