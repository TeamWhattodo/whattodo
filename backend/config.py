from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    fast_model: str = "claude-haiku-4-5-20251001"
    smart_model: str = "claude-sonnet-4-6"

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""
    jira_api_token: str = ""
    jira_base_url: str = ""

    secret_key: str = "dev-secret-key"
    streamlit_port: int = 8501
    use_mock_data: bool = False

    urgency_weight_time: float = 0.35
    urgency_weight_authority: float = 0.25
    urgency_weight_followup: float = 0.20
    urgency_weight_keyword: float = 0.10
    urgency_weight_source: float = 0.10

    collection_limit_per_source: int = 200
    briefing_timeout_seconds: int = 60
    classifier_batch_size: int = 50
    default_absence_threshold_hours: int = 8
    react_max_iterations: int = 5
    react_urgency_threshold: int = 5


settings = Settings()
