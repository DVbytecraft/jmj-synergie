"""Unit tests for the Client domain entity — validation and lifecycle."""
from __future__ import annotations

import uuid

import pytest

from app.domain.entities.client import Client, ClientStatus, ClientType


def _make_client(**overrides) -> Client:
    defaults = dict(
        full_name="Jean Dupont",
        phone="+237600000000",
        client_type=ClientType.INDIVIDUAL,
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return Client(**defaults)


class TestClientValidation:
    def test_empty_full_name_raises(self):
        with pytest.raises(ValueError, match="full_name"):
            _make_client(full_name="  ")

    def test_empty_phone_raises(self):
        with pytest.raises(ValueError, match="phone"):
            _make_client(phone="")

    def test_company_without_company_name_raises(self):
        with pytest.raises(ValueError, match="company_name"):
            _make_client(client_type=ClientType.COMPANY)

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError, match="Invalid email"):
            _make_client(email="not-an-email")

    def test_negative_credit_limit_raises(self):
        with pytest.raises(ValueError, match="credit_limit_cents"):
            _make_client(credit_limit_cents=-1)

    def test_invalid_payment_terms_days_raises(self):
        with pytest.raises(ValueError, match="payment_terms_days"):
            _make_client(payment_terms_days=400)

    def test_valid_company_client(self):
        client = _make_client(client_type=ClientType.COMPANY, company_name="Acme SARL")
        assert client.company_name == "Acme SARL"


class TestClientUpdate:
    def test_update_all_fields(self):
        client = _make_client()
        client.update(
            full_name="New Name",
            phone="+237611111111",
            email="new@example.com",
            company_name="New Co",
            address_line1="123 Rue",
            city="Yaoundé",
            country="GA",
            credit_limit_cents=1000,
            payment_terms_days=45,
            notes="note",
        )
        assert client.full_name == "New Name"
        assert client.phone == "+237611111111"
        assert client.email == "new@example.com"
        assert client.company_name == "New Co"
        assert client.address_line1 == "123 Rue"
        assert client.city == "Yaoundé"
        assert client.country == "GA"
        assert client.credit_limit_cents == 1000
        assert client.payment_terms_days == 45
        assert client.notes == "note"

    def test_update_with_no_fields_is_noop(self):
        client = _make_client()
        original_name = client.full_name
        client.update()
        assert client.full_name == original_name


class TestClientLifecycle:
    def test_deactivate(self):
        client = _make_client()
        client.deactivate()
        assert client.status == ClientStatus.INACTIVE

    def test_deactivate_blacklisted_raises(self):
        client = _make_client()
        client.blacklist("fraud")
        with pytest.raises(ValueError, match="blacklisted"):
            client.deactivate()

    def test_reactivate(self):
        client = _make_client()
        client.deactivate()
        client.reactivate()
        assert client.status == ClientStatus.ACTIVE

    def test_blacklist(self):
        client = _make_client()
        client.blacklist("Fraude suspectée")
        assert client.status == ClientStatus.BLACKLISTED
        assert "BLACKLIST" in client.notes
        assert "Fraude suspectée" in client.notes

    def test_blacklist_empty_reason_raises(self):
        client = _make_client()
        with pytest.raises(ValueError, match="reason"):
            client.blacklist("   ")

    def test_soft_delete(self):
        client = _make_client()
        deleted_by = uuid.uuid4()
        client.soft_delete(deleted_by)
        assert client.is_deleted is True
        assert client.deleted_by == deleted_by
        assert client.deleted_at is not None


class TestClientProperties:
    def test_display_name_prefers_company_name(self):
        client = _make_client(
            client_type=ClientType.COMPANY, company_name="Acme SARL", full_name="Jean"
        )
        assert client.display_name == "Acme SARL"

    def test_display_name_falls_back_to_full_name(self):
        client = _make_client()
        assert client.display_name == client.full_name

    def test_is_active_true_for_fresh_client(self):
        client = _make_client()
        assert client.is_active is True

    def test_is_active_false_when_deleted(self):
        client = _make_client()
        client.soft_delete(uuid.uuid4())
        assert client.is_active is False

    def test_is_active_false_when_inactive(self):
        client = _make_client()
        client.deactivate()
        assert client.is_active is False
