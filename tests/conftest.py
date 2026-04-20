"""Shared fixtures for backend tests."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def reload_failover_module():
    """Restore `backend.llm.failover` after tests that tweak LLM_PROVIDER_ORDER via env + reload."""
    yield
    import backend.llm.failover as failover

    importlib.reload(failover)
