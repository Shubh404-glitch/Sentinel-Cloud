"""Users API (Stage 7: Organization Administration). RoleEnum's own
contract: "ADMIN: manage Users ... within the Organization." List is
available to any authenticated member (seeing your teammates is not a
management action); create/update require ADMIN.

No self-service signup and no email/invite flow exist anywhere in this
system (verified before designing this) -- an ADMIN directly sets a new
user's initial password. There is deliberately no delete endpoint:
users are deactivated (`is_active=False`), never hard-deleted, so
AuditLogEntry.user_id (a nullable FK with ON DELETE SET NULL) still has
a real row to reference for historical entries instead of silently
losing "who did this" -- consistent with AuditLogEntry being append-only
and never rewritten (domain/audit_log_entry.py's own docstring).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user, require_role
from sentinelscan_cloud.api.schemas.read_models import (
    PaginatedResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.audit_log_entry_repository import AuditLogEntryRepository
from sentinelscan_cloud.repositories.user_repository import UserRepository
from sentinelscan_cloud.security.password_hashing import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(u: User) -> UserResponse:
    return UserResponse(
        id=u.id, email=u.email, display_name=u.display_name, role=u.role.value, is_active=u.is_active,
        created_at=u.created_at,
    )


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[UserResponse]:
    repo = UserRepository(session, organization_id=current_user.organization_id)
    users = await repo.list_all(limit=limit, offset=offset)
    total = await repo.count_all()
    return PaginatedResponse(items=[_to_response(u) for u in users], total=total, limit=limit, offset=offset)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    try:
        role = RoleEnum(body.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid role {body.role!r}")

    user = User(
        organization_id=current_user.organization_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        role=role,
    )
    audit_repo = AuditLogEntryRepository(session, organization_id=current_user.organization_id)
    session.add(user)

    try:
        await session.flush()
    except IntegrityError:
        # email is globally unique (Section 15/domain/user.py), not just
        # within this Organization -- a collision with ANY organization's
        # user is a real, expected case, not a bug. Let the database be
        # the source of truth rather than a separate pre-check-then-insert
        # (which has its own race condition and would need to reuse
        # UserRepository.get_by_email outside the auth path it's
        # documented to be restricted to).
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a user with this email already exists")

    audit_repo.record(
        action="user.created", affected_entity_type="User", affected_entity_id=user.id, user_id=current_user.id,
        metadata={"email": user.email, "role": user.role.value},
    )
    await session.commit()
    await session.refresh(user)
    return _to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    repo = UserRepository(session, organization_id=current_user.organization_id)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        try:
            new_role = RoleEnum(body.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"invalid role {body.role!r}")
        if new_role != user.role and user.id == current_user.id:
            # An ADMIN demoting themselves with no other ADMIN in the
            # loop is exactly how an Organization silently loses all
            # administrative access -- reject it outright rather than
            # leave the Organization unmanageable. (A future stage could
            # allow it once >1 ADMIN is confirmed to exist; not
            # implemented here since that check has its own tenant-
            # isolation subtlety worth its own review.)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot change your own role -- have another admin do it",
            )
        user.role = new_role
    if body.is_active is not None:
        if not body.is_active and user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot deactivate your own account")
        user.is_active = body.is_active

    audit_repo = AuditLogEntryRepository(session, organization_id=current_user.organization_id)
    audit_repo.record(
        action="user.updated", affected_entity_type="User", affected_entity_id=user.id, user_id=current_user.id,
        metadata=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    await session.refresh(user)
    return _to_response(user)
