import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.config import Settings
from src.providers.azure_openai import AzureOpenAIProvider
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.claude import ClaudeProvider
from src.providers.factory import create_llm_provider, create_vision_provider
from src.providers.gemini import GeminiProvider, _EXTRACT_SYSTEM, _MANUAL_SYSTEM  # noqa: F401
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def test_ollama_provider_implements_protocol() -> None:
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:7b")
    assert isinstance(provider, LLMProvider)


def test_ollama_vision_provider_implements_protocol() -> None:
    provider = OllamaVisionProvider(host="http://localhost:11434", vision_model="llama3.2-vision")
    assert isinstance(provider, VisionLLMProvider)


def test_claude_provider_implements_protocol() -> None:
    provider = ClaudeProvider(api_key="dummy")
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)


def test_gemini_provider_implements_protocol() -> None:
    provider = GeminiProvider(api_key="dummy")
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)


def test_azure_openai_provider_implements_protocol() -> None:
    provider = AzureOpenAIProvider(
        api_key="dummy", endpoint="https://x.openai.azure.com/", deployment="gpt-4o"
    )
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, VisionLLMProvider)


def test_factory_returns_gemini_by_default() -> None:
    # コード定義のデフォルトが gemini であることを確認（.env の影響を受けない）
    assert Settings.model_fields["llm_provider"].default == "gemini"
    settings = Settings(llm_provider="gemini")
    provider = create_llm_provider(settings)
    assert isinstance(provider, GeminiProvider)


def test_vision_factory_returns_gemini_by_default() -> None:
    assert Settings.model_fields["llm_vision_provider"].default == "gemini"
    settings = Settings(llm_vision_provider="gemini")
    provider = create_vision_provider(settings)
    assert isinstance(provider, GeminiProvider)


def test_gemini_model_default_is_flash() -> None:
    # コード定義のデフォルトが gemini-2.0-flash であることを確認
    assert Settings.model_fields["gemini_model"].default == "gemini-2.0-flash"


def test_factory_returns_ollama_when_configured() -> None:
    settings = Settings(llm_provider="ollama")
    provider = create_llm_provider(settings)
    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, OllamaProvider)


def test_factory_returns_claude_when_configured() -> None:
    settings = Settings(llm_provider="claude", anthropic_api_key="sk-ant-test")
    provider = create_llm_provider(settings)
    assert isinstance(provider, ClaudeProvider)


def test_vision_factory_returns_ollama_when_configured() -> None:
    settings = Settings(llm_vision_provider="ollama")
    provider = create_vision_provider(settings)
    assert isinstance(provider, VisionLLMProvider)
    assert isinstance(provider, OllamaVisionProvider)


@pytest.mark.asyncio
async def test_extract_tasks_manual_uses_manual_prompt() -> None:
    """source_type='manual' のとき _MANUAL_SYSTEM プロンプトが使われる"""
    provider = GeminiProvider(api_key="dummy")
    mock_resp = MagicMock()
    mock_resp.text = json.dumps([
        {
            "is_task": True,
            "title": "手順1を実行する",
            "assignee_name": None,
            "deadline": None,
            "priority": "medium",
            "category": "その他",
            "visibility": "team",
            "confidence_score": 0.9,
        }
    ])
    with patch.object(
        provider._client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_gen:
        result = await provider.extract_tasks("手順書テキスト", "manual")

    call_config = mock_gen.call_args.kwargs["config"]
    assert call_config.system_instruction == _MANUAL_SYSTEM
    assert len(result) == 1
    assert result[0].title == "手順1を実行する"
    assert result[0].source_type == "manual"


@pytest.mark.asyncio
async def test_extract_tasks_email_uses_extract_prompt() -> None:
    """source_type='email' のとき _EXTRACT_SYSTEM が使われる（既存動作の保護）"""
    provider = GeminiProvider(api_key="dummy")
    mock_resp = MagicMock()
    mock_resp.text = "[]"
    with patch.object(
        provider._client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_gen:
        await provider.extract_tasks("メールテキスト", "email")

    call_config = mock_gen.call_args.kwargs["config"]
    assert call_config.system_instruction == _EXTRACT_SYSTEM
