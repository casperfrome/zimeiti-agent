from app.ai_client import (
    SearchResult,
    calculate_usage_cost,
    perform_web_search,
    search_status_payload,
)


def test_calculate_deepseek_flash_cost_uses_cache_buckets():
    usage = calculate_usage_cost(
        "deepseek",
        "deepseek-v4-flash",
        {
            "prompt_tokens": 150,
            "prompt_cache_hit_tokens": 100,
            "prompt_cache_miss_tokens": 50,
            "completion_tokens": 200,
            "total_tokens": 350,
        },
    )

    assert usage["prompt_tokens"] == 150
    assert usage["prompt_cache_hit_tokens"] == 100
    assert usage["prompt_cache_miss_tokens"] == 50
    assert usage["completion_tokens"] == 200
    assert usage["total_tokens"] == 350
    assert usage["currency"] == "CNY"
    assert usage["estimated_cost_cny"] == 0.000452
    assert "DeepSeek" in usage["pricing_note"]


def test_calculate_deepseek_pro_cost_handles_missing_cache_fields():
    usage = calculate_usage_cost(
        "deepseek",
        "deepseek-v4-pro",
        {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        },
    )

    assert usage["prompt_cache_hit_tokens"] == 0
    assert usage["prompt_cache_miss_tokens"] == 1000
    assert usage["estimated_cost_cny"] == 0.006


def test_calculate_unknown_model_reports_tokens_without_cost():
    usage = calculate_usage_cost(
        "kimi",
        "moonshot-v1-32k",
        {
            "prompt_tokens": 20,
            "completion_tokens": 30,
            "total_tokens": 50,
        },
    )

    assert usage["prompt_tokens"] == 20
    assert usage["completion_tokens"] == 30
    assert usage["total_tokens"] == 50
    assert usage["estimated_cost_cny"] is None
    assert usage["currency"] is None
    assert usage["pricing_note"] == "未配置价格"


def test_perform_web_search_retries_with_local_proxy(monkeypatch):
    calls = []
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    class FakeResponse:
        text = """
        <html>
          <a class="result__a" href="https://example.com/a">Result A</a>
          <a class="result__snippet">Snippet A</a>
        </html>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, params, headers, timeout, proxies=None):
        calls.append(proxies)
        if proxies is None:
            raise RuntimeError("network blocked")
        return FakeResponse()

    monkeypatch.setattr("app.ai_client.requests.get", fake_get)

    status, results = perform_web_search("短视频选题", max_results=1)

    assert calls == [None, {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}]
    assert status.enabled is True
    assert status.used is True
    assert status.warning is None
    assert results == [SearchResult(title="Result A", url="https://example.com/a", snippet="Snippet A")]


def test_perform_web_search_retries_local_proxy_after_env_proxy_fails(monkeypatch):
    calls = []
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")

    class FakeResponse:
        text = """
        <html>
          <a class="result__a" href="https://example.com/b">Result B</a>
          <a class="result__snippet">Snippet B</a>
        </html>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, params, headers, timeout, proxies=None):
        calls.append(proxies)
        if proxies != {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}:
            raise RuntimeError("env proxy blocked")
        return FakeResponse()

    monkeypatch.setattr("app.ai_client.requests.get", fake_get)

    status, results = perform_web_search("短视频选题", max_results=1)

    assert calls == [None, {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}]
    assert status.enabled is True
    assert status.used is True
    assert status.warning is None
    assert results == [SearchResult(title="Result B", url="https://example.com/b", snippet="Snippet B")]


def test_perform_web_search_failure_returns_warning(monkeypatch):
    calls = []
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)

    def fake_get(url, params, headers, timeout, proxies=None):
        calls.append(proxies)
        raise RuntimeError("network unavailable")

    monkeypatch.setattr("app.ai_client.requests.get", fake_get)

    status, results = perform_web_search("短视频选题", max_results=1)

    assert calls == [None, {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}]
    assert status.enabled is True
    assert status.used is False
    assert status.warning is not None
    assert "联网搜索失败" in status.warning
    assert results == []


def test_search_status_payload_reports_disabled():
    payload = search_status_payload(enabled=False, used=False, warning=None)

    assert payload == {"enabled": False, "used": False, "warning": None}
