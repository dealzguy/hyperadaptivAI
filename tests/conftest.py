"""pytest configuration for Phase A tests.

Integration tests (marked @pytest.mark.integration) require a running stack:
  podman compose -f deploy/compose.yaml up -d
  # wait for temporal to be ready
  pytest tests/ -m integration

Unit tests run without a live stack.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a running compose stack (temporal, postgres-business)",
    )
