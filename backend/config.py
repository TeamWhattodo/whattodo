from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "openai"  # "anthropic" | "openai"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # fast_model: str = "claude-haiku-4-5-20251001"
    # smart_model: str = "claude-sonnet-4-6"
    fast_model: str = "gpt-4o-mini"
    smart_model: str = "gpt-4o"

    gmail_client_id: str = ""
    gmail_client_secret: str = ""

    slack_bot_token: str = ""
    slack_bot_user_id: str = ""
    slack_team_id: str = ""

    jira_api_token: str = ""
    jira_email: str = ""
    jira_base_url: str = ""

    notion_api_token: str = ""
    github_token: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


if __name__ == "__main__":
    print("LLM_PROVIDER:", settings.llm_provider)
    print("FAST_MODEL:", settings.fast_model)
    print("SMART_MODEL:", settings.smart_model)
