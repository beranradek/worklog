"""Pytest configuration and fixtures."""

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set required environment variables for tests."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = MagicMock()
    client.table.return_value.select.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = []
    return client
