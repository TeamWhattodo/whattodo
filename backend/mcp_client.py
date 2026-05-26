"""
MCP 서버 설정. .env에 토큰이 입력된 서버만 자동으로 활성화된다.

필수 패키지:
  Notion  : npx -y @notionhq/notion-mcp-server
  Slack   : npx -y @modelcontextprotocol/server-slack
  Jira    : uvx mcp-atlassian
  GitHub  : npx -y @modelcontextprotocol/server-github
"""
import sys
from backend.config import settings

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
                "OPENAPI_MCP_HEADERS": (
                    f'{{"Authorization": "Bearer {settings.notion_api_token}",'
                    f' "Notion-Version": "2022-06-28"}}'
                )
            },
        }

    if settings.slack_bot_token and settings.slack_team_id:
        config["slack"] = {
            "command": _NPX_CMD,
            "args": _NPX_PREFIX + ["-y", "@modelcontextprotocol/server-slack"],
            "transport": "stdio",
            "env": {
                "SLACK_BOT_TOKEN": settings.slack_bot_token,
                "SLACK_TEAM_ID": settings.slack_team_id,
            },
        }

    if settings.jira_api_token and settings.jira_email and settings.jira_base_url:
        config["jira"] = {
            "command": "uvx",
            "args": ["mcp-atlassian"],
            "transport": "stdio",
            "env": {
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
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_token},
        }

    return config


MCP_SERVER_CONFIG: dict = _build_config()


async def load_mcp_tools() -> list:
    """서버별로 독립 연결해 툴을 수집한다. 한 서버가 실패해도 나머지는 계속 로드한다."""
    if not MCP_SERVER_CONFIG:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient
    tools: list = []
    for name, cfg in MCP_SERVER_CONFIG.items():
        try:
            client = MultiServerMCPClient({name: cfg})
            tools.extend(await client.get_tools())
        except Exception as e:
            print(f"[MCP] '{name}' 연결 실패 (건너뜀): {e}")
    return tools
