
from src.providers.azure_openai import AzureOpenAIProvider
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.claude import ClaudeProvider
from src.providers.gemini import GeminiProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def test_ollama_provider_implements_protocol() -> None:
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:14b")
    assert isinstance(provider, LLMProvider)


def test_ollama_vision_provider_implements_protocol() -> None:
    provider = OllamaVisionProvider(
        host="http://localhost:11434", vision_model="llama3.2-vision"
    )
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
