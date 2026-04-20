"""
Sequential multi-provider LLM failover: Gemini → OpenAI → Upstage (order configurable).

Used for JSON-mode chat completions (interview endpoints, RAG query rewriting).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class AllProvidersFailed(RuntimeError):
    """Raised when every configured provider fails or is unavailable."""


def _sanitize(text: str) -> str:
    """Remove lone surrogates — avoids UTF-8 errors with some PDF/emoji payloads."""
    return "".join(ch for ch in text if not (0xD800 <= ord(ch) <= 0xDFFF))


def _provider_order() -> list[str]:
    raw = os.getenv("LLM_PROVIDER_ORDER", "gemini,openai,upstage")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _timeout_sec() -> float:
    return float(os.getenv("LLM_TIMEOUT_SEC", "60"))


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _upstage_model() -> str:
    return os.getenv("UPSTAGE_MODEL", "solar-pro")


def _upstage_base_url() -> str:
    return os.getenv("UPSTAGE_API_BASE", "https://api.upstage.ai/v1")


def _try_gemini(system: str, user: str, timeout: float) -> Optional[str]:
    key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        logger.warning("google-genai not installed; skip Gemini provider")
        return None
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=_gemini_model(),
            contents=user,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            ),
        )
        text = (response.text or "").strip()
        return text if text else None
    except Exception as exc:
        logger.warning("Gemini generation failed: %s", exc)
        return None


def _try_openai_compatible(
    *,
    api_key: str,
    base_url: Optional[str],
    model: str,
    system: str,
    user: str,
    timeout: float,
) -> Optional[str]:
    try:
        kwargs = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "").strip()
        return content if content else None
    except Exception as exc:
        logger.warning("OpenAI-compatible generation failed (%s): %s", model, exc)
        return None


def _try_openai(
    system: str, user: str, timeout: float, model: Optional[str] = None
) -> Optional[str]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return None
    return _try_openai_compatible(
        api_key=key,
        base_url=None,
        model=model or _openai_model(),
        system=system,
        user=user,
        timeout=timeout,
    )


def _try_upstage(system: str, user: str, timeout: float) -> Optional[str]:
    key = os.getenv("UPSTAGE_API_KEY", "")
    if not key:
        return None
    return _try_openai_compatible(
        api_key=key,
        base_url=_upstage_base_url(),
        model=_upstage_model(),
        system=system,
        user=user,
        timeout=timeout,
    )


def generate_chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    openai_model_override: Optional[str] = None,
) -> tuple[str, str]:
    """
    Return (raw_json_text, provider_name) using the first successful provider.

    Providers are tried in LLM_PROVIDER_ORDER (default: gemini, openai, upstage).
    openai_model_override: when the OpenAI provider is selected, use this model id
    (e.g. RAG_REWRITE_MODEL) instead of OPENAI_MODEL.
    """
    system = _sanitize(system_prompt)
    user = _sanitize(user_prompt)
    timeout = _timeout_sec()
    errors: list[str] = []

    for name in _provider_order():
        if name == "gemini":
            out = _try_gemini(system, user, timeout)
            if out:
                try:
                    json.loads(out)
                except json.JSONDecodeError:
                    errors.append("gemini: invalid JSON in response")
                    continue
                return _sanitize(out), "gemini"
            errors.append("gemini: unavailable or failed")
        elif name == "openai":
            omodel = openai_model_override or _openai_model()
            out = _try_openai(system, user, timeout, model=omodel)
            if out:
                try:
                    json.loads(out)
                except json.JSONDecodeError:
                    errors.append("openai: invalid JSON in response")
                    continue
                return _sanitize(out), "openai"
            errors.append("openai: unavailable or failed")
        elif name == "upstage":
            out = _try_upstage(system, user, timeout)
            if out:
                try:
                    json.loads(out)
                except json.JSONDecodeError:
                    errors.append("upstage: invalid JSON in response")
                    continue
                return _sanitize(out), "upstage"
            errors.append("upstage: unavailable or failed")
        else:
            errors.append(f"{name}: unknown provider (ignored)")

    raise AllProvidersFailed("; ".join(errors) if errors else "no providers configured")
