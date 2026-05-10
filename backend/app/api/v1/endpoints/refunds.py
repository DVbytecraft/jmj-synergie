"""
Refunds API — request, approve, reject, list.

Endpoints :
  POST   /refunds/                    → Demander un remboursement
  GET    /refunds/                    → Lister les remboursements
  GET    /refunds/{id}                → Détail d'un remboursement
  POST   /refunds/{id}/approve        → Approuver (manager+)
  POST   /refunds/{id}/reject         → Rejeter (manager+)
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    CurrentUser, ManagerUser,
    get_request_refund_uc, get_approve_refund_uc,
    get_reject_refund_uc, get_list_refunds_uc,
)
from app.application.dto.payment_dto import (
    RequestRefundDTO, ApproveRefundDTO, RejectRefundDTO, RefundResponseDTO,
)
from app.application.use_cases.refund.manage_refund import (
    RequestRefundUseCase, ApproveRefundUseCase,
    RejectRefundUseCase, ListRefundsUseCase,
)

router = APIRouter()


@router.post(
    "/",
    response_model=RefundResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Demander un remboursement",
)
async def request_refund(
    body: RequestRefundDTO,
    current_user: CurrentUser,
    uc: Annotated[RequestRefundUseCase, Depends(get_request_refund_uc)],
) -> RefundResponseDTO:
    return await uc.execute(body, current_user.id)


@router.get(
    "/",
    response_model=dict,
    summary="Lister les remboursements",
)
async def list_refunds(
    current_user: CurrentUser,
    uc: Annotated[ListRefundsUseCase, Depends(get_list_refunds_uc)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    refund_status: str | None = Query(None, alias="status"),
) -> dict:
    return await uc.execute(skip=skip, limit=limit, status=refund_status)


@router.get(
    "/{refund_id}",
    response_model=RefundResponseDTO,
    summary="Détail d'un remboursement",
)
async def get_refund(
    refund_id: UUID,
    current_user: CurrentUser,
    uc: Annotated[ListRefundsUseCase, Depends(get_list_refunds_uc)],
) -> RefundResponseDTO:
    from fastapi import HTTPException
    from app.application.use_cases.refund.manage_refund import _to_response
    refund = await uc._refund_repo.get_by_id(refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Remboursement introuvable")
    return _to_response(refund)


@router.post(
    "/{refund_id}/approve",
    response_model=RefundResponseDTO,
    summary="Approuver un remboursement",
)
async def approve_refund(
    refund_id: UUID,
    body: ApproveRefundDTO,
    current_user: ManagerUser,
    uc: Annotated[ApproveRefundUseCase, Depends(get_approve_refund_uc)],
) -> RefundResponseDTO:
    return await uc.execute(refund_id, body, current_user.id)


@router.post(
    "/{refund_id}/reject",
    response_model=RefundResponseDTO,
    summary="Rejeter un remboursement",
)
async def reject_refund(
    refund_id: UUID,
    body: RejectRefundDTO,
    current_user: ManagerUser,
    uc: Annotated[RejectRefundUseCase, Depends(get_reject_refund_uc)],
) -> RefundResponseDTO:
    return await uc.execute(refund_id, body, current_user.id)
