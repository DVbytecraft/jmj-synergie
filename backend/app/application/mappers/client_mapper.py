"""Client mapper — domain entity ↔ DTO."""
from app.domain.entities.client import Client, ClientType
from app.application.dto.client_dto import CreateClientDTO, ClientResponseDTO


class ClientMapper:

    @staticmethod
    def from_create_dto(dto: CreateClientDTO, created_by_id, organization_id, code: str) -> Client:
        return Client(
            full_name=dto.full_name,
            phone=dto.phone,
            client_type=ClientType(dto.client_type),
            created_by=created_by_id,
            organization_id=organization_id,
            company_name=dto.company_name,
            tax_id=dto.tax_id,
            email=str(dto.email) if dto.email else None,
            address_line1=dto.address_line1,
            city=dto.city,
            country=dto.country,
            currency=dto.currency,
            credit_limit_cents=dto.credit_limit_cents,
            payment_terms_days=dto.payment_terms_days,
            default_tax_rate=dto.default_tax_rate,
            notes=dto.notes,
            code=code,
        )

    @staticmethod
    def to_response_dto(client: Client) -> ClientResponseDTO:
        return ClientResponseDTO(
            id=client.id,
            code=client.code,
            client_type=client.client_type.value,
            status=client.status.value,
            full_name=client.full_name,
            company_name=client.company_name,
            tax_id=client.tax_id,
            email=client.email,
            phone=client.phone,
            address_line1=client.address_line1,
            city=client.city,
            country=client.country,
            currency=client.currency,
            credit_limit_cents=client.credit_limit_cents,
            payment_terms_days=client.payment_terms_days,
            default_tax_rate=client.default_tax_rate,
            notes=client.notes,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )
