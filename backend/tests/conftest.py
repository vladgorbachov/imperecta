"""Pytest fixtures and configuration."""

import os

import pytest


@pytest.fixture(scope="session")
def test_database_url():
    """Use DATABASE_URL from env or default test DB."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/priceradar_test",
    )
