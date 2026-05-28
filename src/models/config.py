import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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
    dept_plan_map: str = "{}"

    # アクセス制限（空の場合は全ユーザーを処理）
    # カンマ区切りの Azure AD ユーザーID または UPN（例: uid-1,uid-2）
    allowed_user_ids: str = ""

    # Langfuse
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # ポーリング
    polling_interval_seconds: int = 300
    auto_create_threshold: float = 0.8
    manual_review_threshold: float = 0.5

    # LLMプロバイダー
    llm_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "gemini"
    llm_vision_provider: Literal["ollama", "claude", "gemini", "azure_openai"] = "gemini"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_vision_model: str = "llama3.2-vision"

    # Claude
    anthropic_api_key: str = ""

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://autoticket:autoticket@localhost:5432/autoticket"
    # フロントエンド
    azure_client_id_frontend: str = ""
    frontend_url: str = "http://localhost:5173"
    # 開発モード（JWT検証スキップ・X-Dev-Userヘッダーを受け入れる。本番では必ず false）
    dev_mode: bool = False
    # Forms / SharePoint
    sharepoint_site_id: str = ""
    forms_list_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("dept_plan_map")
    @classmethod
    def validate_dept_plan_map(cls, value: str) -> str:
        """Validate that dept_plan_map is valid JSON and contains a dict."""
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"dept_plan_map must be valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("dept_plan_map must be a JSON object (dict)")
        return value

    def get_allowed_user_ids(self) -> list[str]:
        """許可ユーザー ID のリストを返す。空の場合は空リスト（= 全ユーザー処理）。"""
        if not self.allowed_user_ids.strip():
            return []
        return [uid.strip() for uid in self.allowed_user_ids.split(",") if uid.strip()]

    def get_dept_plan_map(self) -> dict[str, str]:
        """Parse and return dept_plan_map as a dictionary."""
        parsed = json.loads(self.dept_plan_map)
        return parsed if isinstance(parsed, dict) else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
