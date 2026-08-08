"""
Stage 5 integration tests: the read-side API (Dashboard, Projects,
Assets, Reports, Risk Center, Recommendations, Timeline, Analytics,
Search) against a real PostgreSQL database, after a real ingestion +
Intelligence Processing run has populated data to read back.

Environment Blocked in this sandbox (see Stage 5 Completion Report) --
same root cause as every prior stage's integration tests: no network
access to install the dependency stack, no reachable PostgreSQL.

Note on response shapes: every list endpoint returns a PaginatedResponse
envelope (`{"items": [...], "total": N, "limit": L, "offset": O}`), not
a bare JSON array -- tests below index into `body["items"]` accordingly.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.ingestion.job_queue import InProcessJobQueue
from sentinelscan_cloud.ingestion.object_storage import LocalFilesystemObjectStorage
from sentinelscan_cloud.ingestion.schema_validation.validator import SCHEMA_DIR
from sentinelscan_cloud.ingestion.workflow import ingest_report
from sentinelscan_cloud.intelligence.queue_registration import register_intelligence_processing_handler

pytestmark = pytest.mark.anyio

EXAMPLES_DIR = SCHEMA_DIR / "v1" / "examples"


@pytest.fixture
def wired_job_queue():
    queue = InProcessJobQueue()
    register_intelligence_processing_handler(queue)
    return queue


async def _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue):
    api_key, _raw = await api_key_factory()
    tmp_object_storage = LocalFilesystemObjectStorage(tmp_path / "reports")
    raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()
    return await ingest_report(
        db_session, organization_id=project.organization_id, project_id=project.id,
        ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
        object_storage=tmp_object_storage, job_queue=wired_job_queue,
    )


class TestDashboard:
    async def test_dashboard_reflects_ingested_data(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get("/dashboard", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["project_count"] >= 1
        assert body["asset_count"] == 2
        assert body["open_finding_count"] == 2
        assert sum(body["risk_distribution"].values()) == 2
        assert len(body["recent_timeline_events"]) >= 2  # 2 asset_added events


class TestProjectsAndAssets:
    async def test_list_projects_scoped_to_organization(self, client: AsyncClient, project: Project, auth_headers):
        response = await client.get("/projects", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        ids = [p["id"] for p in body["items"]]
        assert str(project.id) in ids

    async def test_create_update_delete_project(self, client: AsyncClient, organization, auth_headers):
        create_response = await client.post(
            "/projects", headers=auth_headers, json={"name": "New Project", "criticality": "high"}
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["criticality"] == "high"

        update_response = await client.patch(
            f"/projects/{created['id']}", headers=auth_headers, json={"criticality": "critical"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["criticality"] == "critical"

        delete_response = await client.delete(f"/projects/{created['id']}", headers=auth_headers)
        assert delete_response.status_code == 204

        get_response = await client.get(f"/projects/{created['id']}", headers=auth_headers)
        assert get_response.status_code == 404

    async def test_project_statistics(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["asset_count"] == 2
        assert body["open_finding_count"] == 2
        assert body["average_asset_score"] is not None

    async def test_asset_detail_includes_knowledge_depth(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        assets_response = await client.get(f"/projects/{project.id}/assets", headers=auth_headers)
        assert assets_response.status_code == 200
        body = assets_response.json()
        assert body["total"] == 2
        assets = body["items"]
        assert len(assets) == 2
        assert all(a["knowledge_depth_label"] == "baseline established" for a in assets)
        assert all(a["current_score"] is not None for a in assets)

        detail_response = await client.get(f"/assets/{assets[0]['id']}", headers=auth_headers)
        assert detail_response.status_code == 200
        assert detail_response.json()["knowledge_depth_report_count"] == 1

    async def test_asset_score_history(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        assets_response = await client.get(f"/projects/{project.id}/assets", headers=auth_headers)
        asset_id = assets_response.json()["items"][0]["id"]

        history_response = await client.get(f"/assets/{asset_id}/history", headers=auth_headers)
        assert history_response.status_code == 200
        history = history_response.json()
        assert len(history) == 1
        assert "deductions" in history[0]["contributing_factors"]

    async def test_asset_identifier_filter(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(
            f"/projects/{project.id}/assets?identifier_contains=10.20.30", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert all("10.20.30" in a["identifier"] for a in body["items"])


class TestRiskCenterAndRecommendations:
    async def test_risk_center_lists_open_findings(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}/risk-center", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert all(f["is_resolved"] is not True for f in body["items"])

    async def test_risk_center_severity_filter(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}/risk-center?severity=high", headers=auth_headers)
        assert response.status_code == 200
        assert all(f["severity"] == "high" for f in response.json()["items"])

    async def test_risk_center_status_all_includes_resolved(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        import json as _json
        payload = _json.loads((EXAMPLES_DIR / "discover_example.json").read_bytes())
        api_key, _raw = await api_key_factory()
        storage = LocalFilesystemObjectStorage(tmp_path / "reports")

        await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=_json.dumps(payload).encode(),
            object_storage=storage, job_queue=wired_job_queue,
        )
        payload_2 = _json.loads(_json.dumps(payload))
        payload_2["findings"].pop()
        await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=_json.dumps(payload_2).encode(),
            object_storage=storage, job_queue=wired_job_queue,
        )

        response = await client.get(f"/projects/{project.id}/risk-center?status=all", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert any(f["is_resolved"] for f in body["items"]), "status=all must include resolved findings"

    async def test_risk_center_invalid_status_rejected(
        self, client: AsyncClient, project: Project, auth_headers
    ):
        response = await client.get(f"/projects/{project.id}/risk-center?status=bogus", headers=auth_headers)
        assert response.status_code == 422

    async def test_recommendations_are_ranked(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        assets_response = await client.get(f"/projects/{project.id}/assets", headers=auth_headers)
        asset_id = assets_response.json()["items"][0]["id"]

        response = await client.get(f"/assets/{asset_id}/recommendations", headers=auth_headers)
        assert response.status_code == 200
        recs = response.json()["items"]
        ranks = [r["priority_rank"] for r in recs]
        assert ranks == sorted(ranks)


class TestTimelineAnalyticsSearch:
    async def test_project_timeline_has_asset_added_events(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}/timeline", headers=auth_headers)
        assert response.status_code == 200
        event_types = {e["event_type"] for e in response.json()["items"]}
        assert "asset_added" in event_types

    async def test_project_timeline_event_type_filter(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(
            f"/projects/{project.id}/timeline?event_type=asset_added", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert all(e["event_type"] == "asset_added" for e in body["items"])

    async def test_organization_timeline(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get("/organization/timeline", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    async def test_analytics_reflects_open_findings(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}/analytics", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_open_findings"] == 2
        assert body["total_assets"] == 2
        assert body["average_asset_score"] is not None

    async def test_analytics_score_trend(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get(f"/projects/{project.id}/analytics/trends", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()["score_trend"]) >= 1

    async def test_search_finds_asset_by_identifier(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, api_key_factory, tmp_path,
        wired_job_queue, auth_headers,
    ):
        await _seed_ingested_report(db_session, project, api_key_factory, tmp_path, wired_job_queue)
        response = await client.get("/search?q=10.20.30", headers=auth_headers)
        assert response.status_code == 200
        assert any(r["entity_type"] == "asset" for r in response.json())


class TestTenantIsolation:
    async def test_cannot_read_another_organizations_project(
        self, client: AsyncClient, db_session: AsyncSession, organization: Organization, auth_headers
    ):
        other_org = Organization(name="Other Org", slug="other-org-isolation-test")
        db_session.add(other_org)
        await db_session.flush()
        other_project = Project(organization_id=other_org.id, name="Other Project")
        db_session.add(other_project)
        await db_session.flush()

        response = await client.get(f"/projects/{other_project.id}", headers=auth_headers)
        assert response.status_code == 404, "a Project belonging to a different Organization must be invisible"

    async def test_cannot_list_another_organizations_assets(
        self, client: AsyncClient, db_session: AsyncSession, organization: Organization, auth_headers
    ):
        other_org = Organization(name="Other Org 2", slug="other-org-isolation-test-2")
        db_session.add(other_org)
        await db_session.flush()
        other_project = Project(organization_id=other_org.id, name="Other Project 2")
        db_session.add(other_project)
        await db_session.flush()

        response = await client.get(f"/projects/{other_project.id}/assets", headers=auth_headers)
        assert response.status_code == 404, "listing assets of a Project in a different Organization must 404"
