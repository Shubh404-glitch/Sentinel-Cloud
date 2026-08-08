"""Repository for Project, scoped by Organization (Section 15)."""
from __future__ import annotations

from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.repositories.base import OrganizationScopedRepository


class ProjectRepository(OrganizationScopedRepository[Project]):
    model = Project
    organization_scope_column = Project.organization_id
