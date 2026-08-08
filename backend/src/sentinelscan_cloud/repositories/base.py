"""
Generic base repository.

Section 9 (Backend Architecture): the API layer is thin and delegates to
the application/service layer, which reads and writes exclusively
through repositories -- no route handler talks to the ORM session
directly. Section 15 (Security): multi-tenant isolation is enforced at
this layer, not only at the API boundary, so a scoping bug in any single
route can't leak another Organization's data. See
OrganizationScopedRepository below for how that's enforced.
"""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    CRUD foundation shared by every repository. Deliberately minimal:
    Stage 1 only needs enough to prove the pattern and support the
    health-check / connectivity verification; concrete per-entity query
    methods (e.g. "findings for an asset, newest report first") are
    added alongside the features that need them in later stages.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        """
        Stage 5: total row count, independent of any limit/offset --
        every paginated list endpoint returns this alongside its page
        of items (PaginatedResponse) so a client can render "X of Y"
        without fetching every row.
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)


class OrganizationScopedRepository(BaseRepository[ModelT]):
    """
    Base for any repository whose model is scoped to a single
    Organization (directly or, for Asset/Report, ultimately reachable
    from one). Subclasses must set `organization_scope_column` to the
    model's Organization-foreign-key column (or the model's own `id` for
    Organization itself), and every read in this class filters by it --
    Section 15's "scoped at the repository layer, not just checked at
    the API boundary" made concrete.
    """

    organization_scope_column = None

    def __init__(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ):
        super().__init__(session)
        self.organization_id = organization_id

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        print("=" * 80)
        print(">>> OrganizationScopedRepository.get_by_id()")
        print("Repository:", type(self).__name__)
        print("Model:", self.model.__name__)
        print("Organization:", self.organization_id)
        print("Entity:", entity_id)
        print("Organization Scope Column:", self.organization_scope_column)
        print("=" * 80)

        if self.organization_scope_column is None:
            raise NotImplementedError(
                "Subclasses must set organization_scope_column"
            )

        stmt = select(self.model).where(
            self.model.id == entity_id,
            self.organization_scope_column == self.organization_id,
        )

        print("\nGenerated SQLAlchemy statement:")
        print(stmt)
        print("=" * 80)

        result = await self.session.execute(stmt)

        entity = result.scalar_one_or_none()

        print("Query Result:", entity)
        print("=" * 80)

        return entity

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        if self.organization_scope_column is None:
            raise NotImplementedError(
                "Subclasses must set organization_scope_column"
            )

        stmt = (
            select(self.model)
            .where(
                self.organization_scope_column == self.organization_id
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        if self.organization_scope_column is None:
            raise NotImplementedError(
                "Subclasses must set organization_scope_column"
            )

        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(
                self.organization_scope_column == self.organization_id
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()