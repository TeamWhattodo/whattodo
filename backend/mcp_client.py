"""
MCP 서버 설정. .env에 토큰이 입력된 서버만 자동으로 활성화된다.

필수 패키지:
  Notion  : npx -y @notionhq/notion-mcp-server
  Slack   : npx -y @modelcontextprotocol/server-slack
  Jira    : uvx mcp-atlassian
  GitHub  : npx -y @modelcontextprotocol/server-github
"""
import os
import sys
from pathlib import Path
from backend.config import settings

_ENV = dict(os.environ)
_ROOT = Path(__file__).resolve().parent.parent  # 프로젝트 루트

# Windows에서 npx는 .cmd 배치 스크립트이므로 cmd.exe를 경유해야 한다.
if sys.platform == "win32":
    _NPX_CMD, _NPX_PREFIX = "cmd", ["/c", "npx"]
else:
    _NPX_CMD, _NPX_PREFIX = "npx", []


def _build_config() -> dict:
    config: dict = {}

    if settings.notion_api_token:
        config["notion"] = {
            "command": _NPX_CMD,
            "args": _NPX_PREFIX + ["-y", "@notionhq/notion-mcp-server"],
            "transport": "stdio",
            "env": {
                **_ENV,
                "OPENAPI_MCP_HEADERS": (
                    f'{{"Authorization": "Bearer {settings.notion_api_token}",'
                    f' "Notion-Version": "2022-06-28"}}'
                ),
            },
        }

    if settings.slack_bot_token and settings.slack_team_id:
        _slack_entry = str(_ROOT / "node_modules" / "@modelcontextprotocol" / "server-slack" / "dist" / "index.js")
        config["slack"] = {
            "command": "node",
            "args": [_slack_entry],
            "transport": "stdio",
            "env": {
                **_ENV,
                "SLACK_BOT_TOKEN": settings.slack_bot_token,
                "SLACK_TEAM_ID": settings.slack_team_id,
                "SLACK_BOT_USER_ID": settings.slack_bot_user_id,
            },
        }

    if settings.jira_api_token and settings.jira_email and settings.jira_base_url:
        config["jira"] = {
            "command": "uvx",
            "args": ["mcp-atlassian"],
            "transport": "stdio",
            "env": {
                **_ENV,
                "JIRA_URL": settings.jira_base_url,
                "JIRA_USERNAME": settings.jira_email,
                "JIRA_API_TOKEN": settings.jira_api_token,
            },
        }

    if settings.github_token:
        config["github"] = {
            "command": _NPX_CMD,
            "args": _NPX_PREFIX + ["-y", "@modelcontextprotocol/server-github"],
            "transport": "stdio",
            "env": {**_ENV, "GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_token},
        }

    return config


MCP_SERVER_CONFIG: dict = _build_config()

# GC 방지용 — 클라이언트가 살아있어야 MCP 서버 프로세스 연결이 유지된다.
_alive_clients: list = []


async def load_mcp_tools() -> list:
    """서버별로 독립 연결해 툴을 수집한다. 한 서버가 실패해도 나머지는 계속 로드한다."""
    if not MCP_SERVER_CONFIG:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient
    tools: list = []
    for name, cfg in MCP_SERVER_CONFIG.items():
        try:
            client = MultiServerMCPClient({name: cfg})
            server_tools = await client.get_tools()
            tools.extend(server_tools)
            _alive_clients.append(client)  # 연결 유지
        except Exception as e:
            def _print_causes(exc, _name=name):
                subs = getattr(exc, "exceptions", None)
                if subs:
                    for s in subs:
                        _print_causes(s)
                else:
                    print(f"[MCP] '{_name}' 연결 실패: {type(exc).__name__}: {exc}")
            _print_causes(e)
    return tools
