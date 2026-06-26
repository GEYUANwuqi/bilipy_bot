"""Shared pytest fixtures for bilipy_bot framework tests."""

from uuid import UUID

import pytest

from bilipy_bot.app.config import RuntimeConfig


@pytest.fixture
def mock_config() -> RuntimeConfig:
    """Return a RuntimeConfig with test values."""
    return RuntimeConfig(test_key="test_value")


@pytest.fixture
def fixed_uuid() -> UUID:
    """Return a deterministic UUID for test use."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def alternate_uuid() -> UUID:
    """Return a second deterministic UUID."""
    return UUID("00000000-0000-0000-0000-000000000002")
