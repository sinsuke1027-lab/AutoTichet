
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def test_ollama_provider_implements_protocol() -> None:
    provider = OllamaProvider(host="http://localhost:11434", model="qwen2.5:14b")
    assert isinstance(provider, LLMProvider)


def test_ollama_vision_provider_implements_protocol() -> None:
    provider = OllamaVisionProvider(
        host="http://localhost:11434", vision_model="llama3.2-vision"
    )
    assert isinstance(provider, VisionLLMProvider)
