"""
Smoke tests for `backend.llm.failover` — env-driven provider order, unknown names, OpenAI 429 retry path.

`PROVIDER_ORDER` is fixed at import time; tests use `importlib.reload` after `monkeypatch.setenv`.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import RateLimitError


def _rate_limit_error() -> RateLimitError:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(429, request=req)
    return RateLimitError("rate limited", response=resp, body=None)


def test_empty_llm_provider_order_raises_no_providers_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "")
    import backend.llm.failover as failover

    importlib.reload(failover)
    assert failover.PROVIDER_ORDER == []
    with pytest.raises(failover.AllProvidersFailed, match="no providers configured"):
        failover.generate_chat_json('{"role":"system"}', '{"x":1}')


def test_unknown_provider_names_recorded_and_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "foo, bar , baz")
    import backend.llm.failover as failover

    importlib.reload(failover)
    assert failover.PROVIDER_ORDER == ["foo", "bar", "baz"]
    with pytest.raises(failover.AllProvidersFailed) as excinfo:
        failover.generate_chat_json("{}", "{}")
    msg = str(excinfo.value)
    assert "foo: unknown provider" in msg
    assert "bar: unknown provider" in msg
    assert "baz: unknown provider" in msg


def test_openai_rate_limit_twice_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both attempts raise 429 → retry once with sleep, then give up (no successful JSON)."""
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-smoke")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import backend.llm.failover as failover

    importlib.reload(failover)
    sleeps: list[float] = []

    def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    err = _rate_limit_error()
    with (
        patch.object(failover, "OpenAI") as mock_openai_cls,
        patch.object(failover.time, "sleep", side_effect=record_sleep),
    ):
        inst = MagicMock()
        mock_openai_cls.return_value = inst
        inst.chat.completions.create.side_effect = err
        with pytest.raises(failover.AllProvidersFailed) as excinfo:
            failover.generate_chat_json("{}", '{"a":1}')
        assert "openai: unavailable or failed" in str(excinfo.value)
    assert len(sleeps) == 1
    assert sleeps[0] == 1
    assert inst.chat.completions.create.call_count == 2
