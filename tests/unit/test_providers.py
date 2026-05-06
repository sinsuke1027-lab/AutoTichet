from src.models.config import Settings
from src.providers.azure_openai import AzureOpenAIProvider
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.claude import ClaudeProvider
from src.providers.factory import create_llm_provider, create_vision_provider
from src.providers.gemini import GeminiProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def test_ollama_provider_implements_protocol() -> None:
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:14b")
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
