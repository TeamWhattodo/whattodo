import json
from langchain_core.tools import tool
from backend.config import settings


from langchain_core.runnables import RunnableConfig
from backend.db.store import get_session
from backend.db.orm_models import IntegrationCredentialORM
from backend.utils.encryption import decrypt_token
from sqlalchemy import select

def _client(config: RunnableConfig = None, user_id: int = None):
    from jira import JIRA
    
    uid = user_id
    if config:
        thread_id = config.get("configurable", {}).get("thread_id", "")
        if ":" in thread_id:
            try:
                uid = int(thread_id.split(":")[0])
            except ValueError:
                pass

    if uid:
        with get_session() as db:
            token_obj = db.execute(
                select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == uid, IntegrationCredentialORM.source == "jira")
            ).scalar_one_or_none()
            
            if token_obj and token_obj.credentials_data:
                try:
                    decrypted = decrypt_token(token_obj.credentials_data)
                    creds = json.loads(decrypted)
                    return JIRA(server=creds["base_url"], basic_auth=(creds["email"], creds["api_token"]))
                except Exception as e:
                    import logging
                    logging.error(f"Jira DB 토큰 로드 실패: {e}")

    raise RuntimeError("Jira 계정 연동이 필요합니다.")

def _safe(fn):
    try:
        return json.dumps(fn(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def jira_list_projects(config: RunnableConfig) -> str:
    """접근 가능한 Jira 프로젝트 목록을 조회합니다."""
    try:
        projects = _client(config).projects()
        data = [{"id": p.id, "key": p.key, "name": p.name} for p in projects]
        return json.dumps({"ok": True, "projects": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def jira_search_issues(jql: str, config: RunnableConfig, max_results: int = 50) -> str:
    """JQL 쿼리로 Jira 이슈를 검색합니다. 예: project=PROJ AND status=Open"""
    def _fn():
        issues = _client(config).search_issues(
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
def jira_get_issue(issue_key: str, config: RunnableConfig) -> str:
    """Jira 이슈 상세 정보를 조회합니다. issue_key 예: PROJ-123"""
    def _fn():
        i = _client(config).issue(issue_key)
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
def jira_create_issue(project_key: str, summary: str, config: RunnableConfig, description: str = "", issue_type: str = "Task") -> str:
    """Jira 이슈를 생성합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        issue = _client(config).create_issue(fields={
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        })
        return {"ok": True, "key": issue.key, "id": issue.id}
    return _safe(_fn)


@tool
def jira_get_transitions(issue_key: str, config: RunnableConfig) -> str:
    """Jira 이슈에 적용 가능한 상태 전환 목록을 조회합니다. jira_transition_issue 실행 전 호출."""
    def _fn():
        transitions = _client(config).transitions(issue_key)
        return {"ok": True, "transitions": [{"id": t["id"], "name": t["name"]} for t in transitions]}
    return _safe(_fn)


@tool
def jira_update_issue(issue_key: str, config: RunnableConfig, summary: str = "", description: str = "", priority: str = "") -> str:
    """Jira 이슈 필드를 수정합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        fields: dict = {}
        if summary:
            fields["summary"] = summary
        if description:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        _client(config).issue(issue_key).update(fields=fields)
        return {"ok": True, "key": issue_key}
    return _safe(_fn)


@tool
def jira_transition_issue(issue_key: str, transition_id: str, config: RunnableConfig) -> str:
    """Jira 이슈 상태를 전환합니다. transition_id는 jira_get_transitions로 먼저 조회. 반드시 사용자 확인 후 실행."""
    def _fn():
        _client(config).transition_issue(issue_key, transition_id)
        return {"ok": True, "key": issue_key, "transition_id": transition_id}
    return _safe(_fn)


@tool
def jira_delete_issue(issue_key: str, config: RunnableConfig) -> str:
    """Jira 이슈를 삭제합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        _client(config).issue(issue_key).delete()
        return {"ok": True, "key": issue_key}
    return _safe(_fn)


@tool
def jira_add_comment(issue_key: str, comment: str, config: RunnableConfig) -> str:
    """Jira 이슈에 댓글을 추가합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        c = _client(config).add_comment(issue_key, comment)
        return {"ok": True, "id": c.id, "created": c.created}
    return _safe(_fn)


JIRA_TOOLS = [
    jira_list_projects,
    jira_search_issues,
    jira_get_issue,
    jira_get_transitions,
    jira_create_issue,
    jira_update_issue,
    jira_transition_issue,
    jira_delete_issue,
    jira_add_comment,
]
