from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = {"CHANGE_ME_IN_PRODUCTION", "changeme", "secret", ""}
_WEAK_PASSWORDS = {"sales", "postgres", "password", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"
    app_debug: bool = False
    app_log_level: str = "INFO"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    # Set to True only when running behind a trusted reverse proxy that sets X-Forwarded-For
    trusted_proxy: bool = False

    # PostgreSQL
    postgres_user: str = "sales"
    postgres_password: str = "sales"
    postgres_db: str = "sales"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = ""

    # Database
    sql_echo: bool = False

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""

    # Celery
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # JWT
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Google OAuth SSO
    google_client_id: str = ""
    google_client_secret: str = ""
    google_allowed_domains: str = ""  # Comma-separated list of allowed email domains (empty = all)

    # Encryption
    fernet_key: str = ""  # Fernet symmetric key for encrypting API keys at rest

    # External APIs
    firecrawl_api_key: str = ""
    hunter_io_api_key: str = ""
    bedrijfsdata_api_key: str = ""
    apollo_api_key: str = ""
    scrapin_api_key: str = ""
    anthropic_api_key: str = ""
    apify_api_token: str = ""

    # LLM Provider
    llm_provider: str = "anthropic"  # "anthropic", "openrouter", "gemini", or "google_vertex"
    openrouter_api_key: str = ""
    openrouter_model: str = "minimax/minimax-m2.5:free"
    gemini_api_key: str = ""
    gemini_fast_model: str = ""  # default: gemini-2.5-flash
    gemini_strong_model: str = ""  # default: gemini-2.5-pro

    # Google Vertex AI (service account auth)
    google_service_account_key_path: str = ""  # path to JSON key file (local / mounted secret)
    google_service_account_key_json: str = ""  # or paste the JSON content directly (for CI/secrets managers)
    google_vertex_project_id: str = ""
    google_vertex_location: str = "europe-west1"
    google_vertex_fast_model: str = "gemini-3.1-flash-lite-preview"
    google_vertex_strong_model: str = "gemini-3.1-flash-lite-preview"

    # CRM
    crm_provider: str = ""  # "clickup" or "" (none); extensible for future providers

    # ClickUp
    clickup_api_key: str = ""
    clickup_workspace_id: str = ""
    clickup_space_id: str = ""
    clickup_folder_id: str = ""
    clickup_list_id: str = ""  # default list for new lead tasks
    clickup_domain_field_id: str = ""  # custom field ID for domain-based deduplication
    # Person list (ClickUp)
    clickup_person_list_id: str = ""  # list where Person tasks are created
    clickup_person_email_field_id: str = ""
    clickup_person_phone_field_id: str = ""
    clickup_person_linkedin_field_id: str = ""
    clickup_person_surname_field_id: str = ""
    clickup_person_lastname_field_id: str = ""
    clickup_person_role_field_id: str = ""
    # Relationship field IDs
    clickup_contact_relationship_field_id: str = ""  # on person task: "Customer" -> company
    clickup_company_contact_field_id: str = ""  # on company task: "Contact and role" -> persons

    # Frontend
    frontend_url: str = "http://localhost:5173"  # base URL for links in Slack notifications

    # Slack
    slack_webhook_url: str = ""  # primary webhook for immediate alerts
    slack_digest_webhook_url: str = ""  # separate channel for daily/weekly digests
    slack_digest_hour: int = 9  # daily digest send hour (UTC)
    slack_weekly_day: int = 0  # 0=Monday, 6=Sunday

    # Usage limits (cost management)
    max_companies_per_discovery_run: int = 50  # cap on companies added per single run
    max_discovery_runs_per_day: int = 5  # max manual + scheduled runs per day
    max_enrichments_per_day: int = 100  # max enrichment jobs dispatched per day
    max_scrapes_per_day: int = 50  # max scrape jobs dispatched per day
    max_monitoring_companies_per_run: int = 200  # cap on companies monitored per batch run
    daily_api_cost_limit: float = 25.0  # daily cost cap in EUR (0 = unlimited)

    @model_validator(mode="after")
    def _build_database_url(self) -> "Settings":
        """Derive database_url from component parts when not explicitly set."""
        if not self.database_url:
            password = quote_plus(self.postgres_password)
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    @model_validator(mode="after")
    def _build_redis_urls(self) -> "Settings":
        """Derive Redis/Celery URLs from component parts when not explicitly set."""
        if not self.redis_url:
            auth = f":{quote_plus(self.redis_password)}@" if self.redis_password else ""
            self.redis_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/0"
        if not self.celery_broker_url:
            auth = f":{quote_plus(self.redis_password)}@" if self.redis_password else ""
            self.celery_broker_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/0"
        if not self.celery_result_backend:
            auth = f":{quote_plus(self.redis_password)}@" if self.redis_password else ""
            self.celery_result_backend = f"redis://{auth}{self.redis_host}:{self.redis_port}/1"
        return self

    @model_validator(mode="after")
    def _validate_non_dev_settings(self) -> "Settings":
        """Reject weak defaults in any environment other than development."""
        if self.app_env == "development":
            return self

        if not self.fernet_key:
            raise ValueError(
                "FERNET_KEY must be set outside development. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        if self.jwt_secret_key in _WEAK_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value outside development. "
                "Generate one with: openssl rand -hex 32"
            )
        if self.postgres_password in _WEAK_PASSWORDS:
            raise ValueError(
                "POSTGRES_PASSWORD must be set to a secure value outside development"
            )
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false outside development")
        if not self.google_client_id or not self.google_client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set outside development "
                "(Google SSO is the only authentication method)"
            )
        return self


settings = Settings()
