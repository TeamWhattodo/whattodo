"""
Jira 커넥터 — n8n의 Jira 수집(jira getAll) 노드 대응.

Phase 1: 목 데이터 반환.
Phase 2: JIRA REST API v3 (httpx) 실제 호출로 교체.
"""
from datetime import datetime

import httpx

from backend.connectors.base import BaseConnector
from backend.config import settings
from backend.models import WorkItem


class JiraConnector(BaseConnector):
    async def fetch(self, since: datetime, until: datetime) -> list[WorkItem]:
        """
        Phase 2: 실제 Jira REST API 호출.
        GET /rest/api/3/search?jql=assignee=currentUser() AND updated >= {since}
        """
        # TODO: Phase 2 — httpx 기반 실제 API 호출
        # return await self._fetch_real(since, until)
        return self._mock_data(since)

    def _mock_data(self, since: datetime) -> list[WorkItem]:
        return [
            WorkItem(
                source="jira", raw_id="PROJ-401",
                from_email="pm@company.com", from_name="김PM",
                subject="PROJ-401 백엔드 API 스펙 리뷰 요청",
                body_snippet="API 스펙 문서를 검토하고 코멘트를 달아주세요.",
                received_at=since,
            ),
        ]

    async def _fetch_real(self, since: datetime, until: datetime) -> list[WorkItem]:
        # TODO: settings.jira_base_url, settings.jira_api_token 설정 후 활성화
        base_url = getattr(settings, "jira_base_url", "")
        token = getattr(settings, "jira_api_token", "")
        jql = f"assignee = currentUser() AND updated >= '{since.strftime('%Y-%m-%d')}'"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": 50},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
        # TODO: 응답 파싱 후 WorkItem 목록으로 변환
        return []
