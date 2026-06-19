import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./life_admin.db"
    cors_origins: str = "http://localhost:3000"

    secret_key: str = secrets.token_hex(32)
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def use_mock_llm(self) -> bool:
        return not self.openai_api_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
