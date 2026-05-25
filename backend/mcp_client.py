"""
MCP 서버 설정. .env에 토큰이 입력된 서버만 자동으로 활성화된다.

필수 패키지:
  Notion  : npx -y @notionhq/notion-mcp-server
  Slack   : npx -y @modelcontextprotocol/server-slack
  Jira    : uvx mcp-atlassian
  GitHub  : npx -y @modelcontextprotocol/server-github
"""
from backend.config import settings


def _build_config() -> dict:
    config: dict = {}

    if settings.notion_api_token:
        config["notion"] = {
            "command": "npx",
            "args": ["-y", "@notionhq/notion-mcp-server"],
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
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-slack"],
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
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "transport": "stdio",
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_token},
        }

    return config


MCP_SERVER_CONFIG: dict = _build_config()


async def load_mcp_tools() -> list:
    """활성화된 MCP 서버에서 LangChain 툴 목록을 로드한다."""
    if not MCP_SERVER_CONFIG:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient(MCP_SERVER_CONFIG)
    return await client.get_tools()
