from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.application.dto.client_dto import CreateClientDTO, UpdateClientDTO
from app.application.mappers.client_mapper import ClientMapper
from app.application.use_cases.client.create_client import CreateClientUseCase
from app.application.use_cases.client.delete_client import DeleteClientUseCase
from app.application.use_cases.client.get_client import GetClientUseCase, ListClientsUseCase
from app.application.use_cases.client.update_client import UpdateClientUseCase
from app.core.exceptions import BusinessRuleError, DuplicateEntityError, EntityNotFoundError
from app.domain.entities.client import Client, ClientType
from app.domain.entities.order import Order, OrderStatus


def make_client(*, email: str | None = "client@example.com", is_deleted: bool = False) -> Client:
    return Client(
        full_name="Client Test",
        phone="+237600000000",
        client_type=ClientType.INDIVIDUAL,
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email=email,
        code="CLI-001",
        is_deleted=is_deleted,
    )


def make_order(status: OrderStatus) -> Order:
    return Order(
        client_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        order_number="CMD-001",
        status=status,
    )


@pytest.mark.asyncio
async def test_create_client_use_case_creates_and_maps_client() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.generate_code = AsyncMock(return_value="CLI-100")
    repo.save = AsyncMock(side_effect=lambda client: client)

    dto = CreateClientDTO(
        client_type="individual",
        full_name="Alice Client",
        phone="+237699000000",
        email="alice@example.com",
        country="cm",
        currency="xaf",
    )

    result = await CreateClientUseCase(repo).execute(dto, uuid.uuid4(), uuid.uuid4())

    assert result.code == "CLI-100"
    assert result.full_name == "Alice Client"
    assert result.email == "alice@example.com"
    assert result.country == "CM"
    assert result.currency == "XAF"
    repo.get_by_email.assert_awaited_once_with("alice@example.com")
    repo.generate_code.assert_awaited_once()
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_client_use_case_skips_email_check_when_no_email() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.generate_code = AsyncMock(return_value="CLI-101")
    repo.save = AsyncMock(side_effect=lambda client: client)

    dto = CreateClientDTO(
        client_type="individual",
        full_name="Bob Client",
        phone="+237699000001",
    )

    result = await CreateClientUseCase(repo).execute(dto, uuid.uuid4(), uuid.uuid4())

    assert result.code == "CLI-101"
    repo.get_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_client_use_case_rejects_duplicate_email() -> None:
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=make_client())

    dto = CreateClientDTO(
        client_type="individual",
        full_name="Alice Client",
        phone="+237699000000",
        email="alice@example.com",
    )

    with pytest.raises(DuplicateEntityError):
        await CreateClientUseCase(repo).execute(dto, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_get_and_list_clients_use_cases_cover_success_and_not_found() -> None:
    repo = AsyncMock()
    client = make_client()
    repo.get_by_id = AsyncMock(side_effect=[client, None, make_client(is_deleted=True)])
    repo.list = AsyncMock(return_value=([client], 1))

    got = await GetClientUseCase(repo).execute(client.id)
    listed = await ListClientsUseCase(repo).execute(skip=5, limit=10, search="cli")

    assert got.code == "CLI-001"
    assert listed.total == 1
    assert listed.skip == 5
    assert listed.limit == 10
    assert listed.items[0].email == "client@example.com"

    with pytest.raises(EntityNotFoundError):
        await GetClientUseCase(repo).execute(uuid.uuid4())

    with pytest.raises(EntityNotFoundError):
        await GetClientUseCase(repo).execute(uuid.uuid4())


@pytest.mark.asyncio
async def test_update_client_use_case_updates_entity_and_returns_dto() -> None:
    repo = AsyncMock()
    client = make_client()
    repo.get_by_id = AsyncMock(return_value=client)
    repo.save = AsyncMock(side_effect=lambda saved_client: saved_client)

    result = await UpdateClientUseCase(repo).execute(
        client.id,
        UpdateClientDTO(
            full_name="Client Modifie",
            city="Douala",
            country="GA",
            credit_limit_cents=250000,
            notes="VIP",
        ),
    )

    assert result.full_name == "Client Modifie"
    assert result.city == "Douala"
    assert result.country == "GA"
    assert result.credit_limit_cents == 250000
    assert result.notes == "VIP"


@pytest.mark.asyncio
async def test_update_client_use_case_raises_when_client_missing() -> None:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(EntityNotFoundError):
        await UpdateClientUseCase(repo).execute(uuid.uuid4(), UpdateClientDTO(full_name="Xavier"))


@pytest.mark.asyncio
async def test_delete_client_use_case_raises_when_client_missing_or_deleted() -> None:
    client_repo = AsyncMock()
    order_repo = AsyncMock()
    client_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(EntityNotFoundError):
        await DeleteClientUseCase(client_repo, order_repo).execute(uuid.uuid4(), uuid.uuid4())

    client_repo.get_by_id = AsyncMock(return_value=make_client(is_deleted=True))

    with pytest.raises(EntityNotFoundError):
        await DeleteClientUseCase(client_repo, order_repo).execute(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_client_use_case_blocks_active_orders() -> None:
    client_repo = AsyncMock()
    order_repo = AsyncMock()
    client = make_client()
    client_repo.get_by_id = AsyncMock(return_value=client)
    order_repo.list = AsyncMock(return_value=([make_order(OrderStatus.CONFIRMED)], 1))

    with pytest.raises(BusinessRuleError):
        await DeleteClientUseCase(client_repo, order_repo).execute(client.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_client_use_case_allows_archived_and_cancelled_orders_only() -> None:
    client_repo = AsyncMock()
    order_repo = AsyncMock()
    client = make_client()
    deleted_by = uuid.uuid4()
    client_repo.get_by_id = AsyncMock(return_value=client)
    client_repo.save = AsyncMock(side_effect=lambda saved_client: saved_client)
    order_repo.list = AsyncMock(
        return_value=(
            [
                make_order(OrderStatus.CANCELLED),
                make_order(OrderStatus.ARCHIVED),
            ],
            2,
        )
    )

    await DeleteClientUseCase(client_repo, order_repo).execute(client.id, deleted_by)

    assert client.is_deleted is True
    assert client.deleted_by == deleted_by
    client_repo.save.assert_awaited_once_with(client)


def test_client_mapper_round_trip_covers_create_and_response_mapping() -> None:
    dto = CreateClientDTO(
        client_type="company",
        full_name="Entreprise Exemple",
        phone="+237611111111",
        company_name="Entreprise Exemple SARL",
        email="contact@example.com",
        country="cm",
        currency="xaf",
    )

    entity = ClientMapper.from_create_dto(dto, uuid.uuid4(), uuid.uuid4(), "CLI-200")
    result = ClientMapper.to_response_dto(entity)

    assert entity.client_type == ClientType.COMPANY
    assert entity.code == "CLI-200"
    assert result.company_name == "Entreprise Exemple SARL"
    assert result.email == "contact@example.com"
    assert result.country == "CM"
    assert result.currency == "XAF"
