from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure AD
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Microsoft Planner
    planner_group_id: str = ""
    planner_plan_id: str = ""
    company_wide_plan_id: str = ""

    # Langfuse
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # ポーリング
    polling_interval_seconds: int = 300
    auto_create_threshold: float = 0.8
    manual_review_threshold: float = 0.5

    # LLMプロバイダー
    llm_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "ollama"
    llm_vision_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "ollama"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_vision_model: str = "llama3.2-vision"

    # Claude
    anthropic_api_key: str = ""

    # Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
