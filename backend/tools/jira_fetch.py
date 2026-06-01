import json
from langchain_core.tools import tool
from backend.config import settings


def _client():
    from jira import JIRA
    return JIRA(server=settings.jira_base_url, basic_auth=(settings.jira_email, settings.jira_api_token))


def _safe(fn):
    try:
        return json.dumps(fn(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def jira_list_projects() -> str:
    """접근 가능한 Jira 프로젝트 목록을 조회합니다."""
    try:
        projects = _client().projects()
        data = [{"id": p.id, "key": p.key, "name": p.name} for p in projects]
        return json.dumps({"ok": True, "projects": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def jira_search_issues(jql: str, max_results: int = 50) -> str:
    """JQL 쿼리로 Jira 이슈를 검색합니다. 예: project=PROJ AND status=Open"""
    def _fn():
        issues = _client().search_issues(
            jql, maxResults=max_results,
            fields="summary,status,assignee,priority,created,updated,description",
        )
        return {
            "ok": True,
            "total": issues.total,
            "issues": [
                {
                    "key": i.key,
                    "summary": i.fields.summary,
                    "status": i.fields.status.name,
                    "assignee": i.fields.assignee.displayName if i.fields.assignee else None,
                    "priority": i.fields.priority.name if i.fields.priority else None,
                    "created": i.fields.created,
                    "updated": i.fields.updated,
                }
                for i in issues
            ],
        }
    return _safe(_fn)


@tool
def jira_get_issue(issue_key: str) -> str:
    """Jira 이슈 상세 정보를 조회합니다. issue_key 예: PROJ-123"""
    def _fn():
        i = _client().issue(issue_key)
        return {
            "ok": True,
            "key": i.key,
            "summary": i.fields.summary,
            "description": i.fields.description,
            "status": i.fields.status.name,
            "assignee": i.fields.assignee.displayName if i.fields.assignee else None,
            "reporter": i.fields.reporter.displayName if i.fields.reporter else None,
            "priority": i.fields.priority.name if i.fields.priority else None,
            "created": i.fields.created,
            "updated": i.fields.updated,
            "comments": [
                {"author": c.author.displayName, "body": c.body, "created": c.created}
                for c in i.fields.comment.comments
            ],
        }
    return _safe(_fn)


@tool
def jira_create_issue(project_key: str, summary: str, description: str = "", issue_type: str = "Task") -> str:
    """Jira 이슈를 생성합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        issue = _client().create_issue(fields={
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        })
        return {"ok": True, "key": issue.key, "id": issue.id}
    return _safe(_fn)


@tool
def jira_add_comment(issue_key: str, comment: str) -> str:
    """Jira 이슈에 댓글을 추가합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        c = _client().add_comment(issue_key, comment)
        return {"ok": True, "id": c.id, "created": c.created}
    return _safe(_fn)


JIRA_TOOLS = [
    jira_list_projects,
    jira_search_issues,
    jira_get_issue,
    jira_create_issue,
    jira_add_comment,
]
