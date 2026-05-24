import html
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Iterator
from urllib.parse import parse_qs, unquote, urlparse

from openai import OpenAI
import requests
from sqlalchemy.orm import Session

from .models import Model, Provider, SystemPrompt


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchStatus:
    enabled: bool
    used: bool
    warning: str | None = None


@dataclass(frozen=True)
class ChatStreamEvent:
    type: str
    text: str | None = None
    usage: dict[str, Any] | None = None


# Source: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
# Checked 2026-05-23. Prices are RMB per 1M tokens.
DEEPSEEK_PRICING_CNY_PER_MILLION = {
    "deepseek-v4-flash": {
        "input_cache_hit": 0.02,
        "input_cache_miss": 1.0,
        "output": 2.0,
        "note": "DeepSeek 官方价格，按 2026-05-23 文档。",
    },
    "deepseek-v4-pro": {
        "input_cache_hit": 0.025,
        "input_cache_miss": 3.0,
        "output": 6.0,
        "note": "DeepSeek 官方价格，含 2026-05-31 23:59 前 2.5 折活动价。",
    },
}

LOCAL_PROXY = "http://127.0.0.1:10808"


def resolve_model(db: Session, model_id: int | None, purpose: str = "chat") -> Model:
    if model_id is not None:
        m = db.get(Model, model_id)
        if m is None:
            raise ValueError(f"model id {model_id} not found")
        return m
    m = (
        db.query(Model)
        .filter(Model.purpose == purpose, Model.is_default.is_(True))
        .first()
    )
    if m is None:
        raise ValueError(f"no default model configured for purpose={purpose}")
    return m


def resolve_prompt(db: Session, function_key: str, prompt_id: int | None) -> SystemPrompt:
    if prompt_id is not None:
        p = db.get(SystemPrompt, prompt_id)
        if p is None or p.function_key != function_key:
            raise ValueError(f"prompt id {prompt_id} not valid for {function_key}")
        return p
    p = (
        db.query(SystemPrompt)
        .filter(SystemPrompt.function_key == function_key, SystemPrompt.is_default.is_(True))
        .first()
    )
    if p is None:
        raise ValueError(f"no default prompt for {function_key}")
    return p


def get_provider(db: Session, provider_key: str) -> Provider:
    p = db.get(Provider, provider_key)
    if p is None:
        raise ValueError(f"provider {provider_key} not found")
    if not p.api_key:
        raise ValueError(f"provider {provider_key} has no api_key configured")
    return p


def _usage_value(usage: Any, key: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        value = usage.get(key, 0)
    else:
        value = getattr(usage, key, 0)
    return int(value or 0)


def calculate_usage_cost(provider_key: str, model_id: str, usage: Any) -> dict[str, Any]:
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    cache_hit_tokens = _usage_value(usage, "prompt_cache_hit_tokens")
    cache_miss_tokens = _usage_value(usage, "prompt_cache_miss_tokens")
    if prompt_tokens and cache_miss_tokens == 0:
        cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)

    payload: dict[str, Any] = {
        "provider_key": provider_key,
        "model_id": model_id,
        "prompt_tokens": prompt_tokens,
        "prompt_cache_hit_tokens": cache_hit_tokens,
        "prompt_cache_miss_tokens": cache_miss_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_cny": None,
        "currency": None,
        "pricing_note": "未配置价格",
    }

    price = DEEPSEEK_PRICING_CNY_PER_MILLION.get(model_id)
    if provider_key == "deepseek" and price is not None:
        cost = (
            cache_hit_tokens * price["input_cache_hit"]
            + cache_miss_tokens * price["input_cache_miss"]
            + completion_tokens * price["output"]
        ) / 1_000_000
        payload.update(
            estimated_cost_cny=round(cost, 6),
            currency="CNY",
            pricing_note=price["note"],
        )

    return payload


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url = ""
        self._last_result_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        class_name = attr.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._capture_title = True
            self._current_title = []
            self._current_url = _normalize_search_url(attr.get("href", ""))
        elif "result__snippet" in class_name:
            self._capture_snippet = True
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title.append(data)
        elif self._capture_snippet:
            self._current_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_title and tag == "a":
            title = html.unescape(" ".join(self._current_title)).strip()
            if title and self._current_url:
                self.results.append(SearchResult(title=title, url=self._current_url, snippet=""))
                self._last_result_index = len(self.results) - 1
            self._capture_title = False
        elif self._capture_snippet and tag in {"a", "div"}:
            snippet = html.unescape(" ".join(self._current_snippet)).strip()
            if snippet and self._last_result_index is not None:
                result = self.results[self._last_result_index]
                self.results[self._last_result_index] = SearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=snippet,
                )
            self._capture_snippet = False


def _normalize_search_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return url


def perform_web_search(query: str, max_results: int = 3) -> tuple[SearchStatus, list[SearchResult]]:
    attempts: list[dict[str, str] | None] = [
        None,
        {"http": LOCAL_PROXY, "https": LOCAL_PROXY},
    ]

    last_error: Exception | None = None
    for proxies in attempts:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "cn-zh"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
                proxies=proxies,
            )
            resp.raise_for_status()
            parser = _DuckDuckGoParser()
            parser.feed(resp.text)
            results = parser.results[:max_results]
            if results:
                return SearchStatus(enabled=True, used=True), results
            last_error = RuntimeError("未找到可用搜索结果")
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    warning = f"联网搜索失败，已不带搜索资料继续调用 AI: {last_error}"
    return SearchStatus(enabled=True, used=False, warning=warning), []


def search_status_payload(enabled: bool, used: bool, warning: str | None) -> dict[str, Any]:
    return {"enabled": enabled, "used": used, "warning": warning}


def format_search_context(results: list[SearchResult]) -> str:
    if not results:
        return ""
    lines = ["联网搜索参考资料："]
    for idx, result in enumerate(results, start=1):
        lines.append(f"{idx}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   摘要: {result.snippet}")
    lines.append("请结合以上资料回答；如果资料不足，请不要编造。")
    return "\n".join(lines)


def build_user_prompt(user: str, search_results: list[SearchResult]) -> str:
    search_context = format_search_context(search_results)
    if not search_context:
        return user
    return f"{search_context}\n\n用户原始需求：\n{user}"


def stream_chat(
    provider: Provider,
    model_id: str,
    system: str,
    user: str,
    search_results: list[SearchResult] | None = None,
) -> Iterator[ChatStreamEvent]:
    client = OpenAI(api_key=provider.api_key, base_url=provider.base_url)
    user_prompt = build_user_prompt(user, search_results or [])
    stream = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        stream_options={"include_usage": True},
    )
    usage_payload: dict[str, Any] | None = None
    for chunk in stream:
        usage = getattr(chunk, "usage", None)
        if usage:
            usage_payload = calculate_usage_cost(provider.provider_key, model_id, usage)
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            yield ChatStreamEvent(type="delta", text=text)
    yield ChatStreamEvent(type="usage", usage=usage_payload)
