"""Secrets contract seam.

All secrets enter the harness through this module only.
Never read os.environ directly elsewhere in the codebase.
Phase A implementation: EnvSecretsProvider (env vars from Docker env_file).
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretsProvider(Protocol):
    def get(self, key: str) -> str:
        ...


class EnvSecretsProvider:
    """Loads secrets from environment variables.

    Phase A implementation — secrets arrive via Docker env_file (deploy/secrets/secrets.env).
    """

    def get(self, key: str) -> str:
        value = os.environ.get(key)
        if value is None:
            raise RuntimeError(
                f"Required secret {key!r} not found in environment. "
                "Ensure deploy/secrets/secrets.env is populated and mounted."
            )
        return value


_provider: SecretsProvider = EnvSecretsProvider()


def get_secret(key: str) -> str:
    """Get a secret value. All callers use this function — never os.environ directly."""
    return _provider.get(key)


def set_provider(provider: SecretsProvider) -> None:
    """Override the provider — used in tests to inject a mock."""
    global _provider
    _provider = provider
