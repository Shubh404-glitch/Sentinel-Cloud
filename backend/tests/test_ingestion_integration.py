"""
Stage 3 integration tests: the full ingest_report() workflow and the
POST /ingestion/reports endpoint, against a real PostgreSQL database.

Environment Blocked in this sandbox (see Stage 3 Completion Report) --
this sandbox has no network access to install sqlalchemy/asyncpg/
fastapi/httpx/pytest, nor a reachable PostgreSQL server. This file is
complete, real, production-shaped test code for the actual dev/CI
environment that has all of that, following the exact same
transaction-per-test pattern already established in
test_auth_integration.py (Stage 2) via conftest.py's `db_session`/
`client` fixtures.
"""
from __future__ import annotations 

import json
import pathlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.domain.enums import ReportProcessingStatusEnum
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.ingestion.job_queue import InProcessJobQueue
from sentinelscan_cloud.ingestion.object_storage import LocalFilesystemObjectStorage
from sentinelscan_cloud.ingestion.schema_validation.validator import SCHEMA_DIR
from sentinelscan_cloud.ingestion.workflow import IngestionFailed, ingest_report
from sentinelscan_cloud.repositories.asset_repository import AssetRepository
from sentinelscan_cloud.repositories.finding_repository import FindingRepository
from sentinelscan_cloud.repositories.report_repository import ReportRepository

pytestmark = pytest.mark.anyio

EXAMPLES_DIR = SCHEMA_DIR / "v1" / "examples"


@pytest.fixture
def tmp_object_storage(tmp_path: pathlib.Path) -> LocalFilesystemObjectStorage:
    return LocalFilesystemObjectStorage(tmp_path / "reports")


@pytest.fixture
def sync_job_queue() -> InProcessJobQueue:
    queue = InProcessJobQueue()
    received: list[dict] = []
    queue.register_handler("intelligence_processing", received.append)
    queue.received = received  # type: ignore[attr-defined]
    return queue


class TestIngestReportWorkflow:
    async def test_ingest_discover_report_persists_everything(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, sync_job_queue
    ):
        api_key, _raw = await api_key_factory()
        raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()

        summary = await ingest_report(
            db_session,
            organization_id=project.organization_id,
            project_id=project.id,
            ingested_via_api_key_id=api_key.id,
            raw_bytes=raw_bytes,
            object_storage=tmp_object_storage,
            job_queue=sync_job_queue,
        )

        assert summary.asset_count == 2
        assert summary.new_asset_count == 2
        assert summary.finding_count == 2
        assert summary.processing_status == ReportProcessingStatusEnum.PROCESSING.value

        report_repo = ReportRepository(db_session, organization_id=project.organization_id)
        report = await report_repo.get_by_id(summary.report_id)
        assert report is not None
        assert tmp_object_storage.exists(report.raw_blob_storage_key)
        assert json.loads(tmp_object_storage.get(report.raw_blob_storage_key)) == json.loads(raw_bytes)

        assert sync_job_queue.received == [{"report_id": str(summary.report_id)}]

    async def test_ingest_reconciles_asset_by_identifier_on_second_import(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, sync_job_queue
    ):
        api_key, _raw = await api_key_factory()
        raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()

        first = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=sync_job_queue,
        )
        second = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=sync_job_queue,
        )

        assert first.new_asset_count == 2
        assert second.new_asset_count == 0, "re-ingesting the same export must reconcile onto the same Assets"

        asset_repo = AssetRepository(db_session, organization_id=project.organization_id)
        assets = await asset_repo.list_for_project(project.id)
        assert len(assets) == 2, "no duplicate Assets should be created on re-import"

    async def test_ingest_computes_same_fingerprint_on_reimport(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, sync_job_queue
    ):
        api_key, _raw = await api_key_factory()
        raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()

        first = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=sync_job_queue,
        )
        second = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=sync_job_queue,
        )

        finding_repo = FindingRepository(db_session, organization_id=project.organization_id)
        first_findings = await finding_repo.list_for_report(first.report_id)
        second_findings = await finding_repo.list_for_report(second.report_id)

        first_fps = sorted(f.correlation_fingerprint for f in first_findings)
        second_fps = sorted(f.correlation_fingerprint for f in second_findings)
        assert first_fps == second_fps, "same underlying findings across two imports must fingerprint identically"

    async def test_ingest_rejects_malformed_payload_without_persisting_anything(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, sync_job_queue
    ):
        api_key, _raw = await api_key_factory()

        with pytest.raises(IngestionFailed):
            await ingest_report(
                db_session, organization_id=project.organization_id, project_id=project.id,
                ingested_via_api_key_id=api_key.id, raw_bytes=b"not json {{{",
                object_storage=tmp_object_storage, job_queue=sync_job_queue,
            )

        report_repo = ReportRepository(db_session, organization_id=project.organization_id)
        reports = await report_repo.list_for_project(project.id)
        assert reports == [], "a structurally invalid payload must not create any Report row"

    async def test_ingest_rejects_schema_invalid_payload(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, sync_job_queue
    ):
        api_key, _raw = await api_key_factory()
        payload = json.loads((EXAMPLES_DIR / "discover_example.json").read_bytes())
        payload["findings"][0]["severity"] = "not-a-real-severity"

        with pytest.raises(IngestionFailed):
            await ingest_report(
                db_session, organization_id=project.organization_id, project_id=project.id,
                ingested_via_api_key_id=api_key.id, raw_bytes=json.dumps(payload).encode(),
                object_storage=tmp_object_storage, job_queue=sync_job_queue,
            )


class TestIngestionEndpoint:
    async def test_endpoint_requires_api_key(self, client: AsyncClient, project: Project):
        response = await client.post(
            f"/ingestion/reports?project_id={project.id}",
            content=(EXAMPLES_DIR / "discover_example.json").read_bytes(),
        )

        print(response.status_code)
        print(response.text)

        assert response.status_code == 401 

    async def test_endpoint_rejects_project_in_another_organization(
        self, client: AsyncClient, db_session: AsyncSession, api_key_factory, organization
    ):
        # A second Organization/Project the API key does NOT belong to.
        from sentinelscan_cloud.domain.organization import Organization as OrgModel

        other_org = OrgModel(name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}")
        db_session.add(other_org)
        await db_session.flush()
        other_project = Project(organization_id=other_org.id, name="Other Project")
        db_session.add(other_project)
        await db_session.flush()

        api_key, raw_key = await api_key_factory()  # scoped to the default `organization`, not `other_org`

        payload = json.loads(
            (EXAMPLES_DIR / "discover_example.json").read_text(encoding="utf-8")
        )

        response = await client.post(
            f"/ingestion/reports?project_id={other_project.id}",
            headers={"X-API-Key": raw_key,
                "Content-Type": "application/json",},
                content=json.dumps(payload).encode(),
        )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        assert response.status_code == 404, "a Project in a different Organization must not be reachable"

async def test_endpoint_ingests_successfully_with_valid_api_key(
    self, client: AsyncClient, project: Project, api_key_factory
):
    api_key, raw_key = await api_key_factory()

    import json

    payload = json.loads(
        (EXAMPLES_DIR / "discover_example.json").read_text()
    )

    response = await client.post(
        f"/ingestion/reports?project_id={project.id}",
        headers={"X-API-Key": raw_key},
        json=payload,
    )

    print(response.status_code)
    print(response.text)

    assert response.status_code == 201

    body = response.json()
    assert body["asset_count"] == 2
    assert body["finding_count"] == 2

    async def test_endpoint_returns_422_for_schema_invalid_payload(
        self, client: AsyncClient, project: Project, api_key_factory
    ):
        api_key, raw_key = await api_key_factory()
        payload = json.loads((EXAMPLES_DIR / "discover_example.json").read_bytes())
        del payload["scan"]

        response = await client.post(
            f"/ingestion/reports?project_id={project.id}",
            headers={"X-API-Key": raw_key},
            content=json.dumps(payload).encode(),
        )
        assert response.status_code == 422 
