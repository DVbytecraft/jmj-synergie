from __future__ import annotations

import os

import pytest

from scripts import seed


@pytest.fixture(autouse=True)
def clear_admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "ADMIN_NAME",
        "SUPER_ADMIN_EMAIL",
        "SUPER_ADMIN_PASSWORD",
        "SUPER_ADMIN_NAME",
    ):
        monkeypatch.delenv(name, raising=False)


def test_resolve_admin_identity_prefers_legacy_admin_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "LegacyPassw0rd!")
    monkeypatch.setenv("ADMIN_NAME", "Legacy Admin")
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "super@example.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "SuperPassw0rd!")
    monkeypatch.setenv("SUPER_ADMIN_NAME", "Super Admin")

    email, password, full_name = seed._resolve_admin_identity()

    assert email == "admin@example.com"
    assert password == "LegacyPassw0rd!"
    assert full_name == "Legacy Admin"


def test_resolve_admin_identity_supports_super_admin_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "super@example.com")
    monkeypatch.setenv("SUPER_ADMIN_PASSWORD", "SuperPassw0rd!")
    monkeypatch.setenv("SUPER_ADMIN_NAME", "Super Admin")

    email, password, full_name = seed._resolve_admin_identity()

    assert email == "super@example.com"
    assert password == "SuperPassw0rd!"
    assert full_name == "Super Admin"


def test_resolve_admin_identity_requires_credentials() -> None:
    with pytest.raises(SystemExit, match="1"):
        seed._resolve_admin_identity()
