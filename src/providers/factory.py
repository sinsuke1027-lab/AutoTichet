from src.models.config import Settings
from src.providers.azure_openai import AzureOpenAIProvider
from src.providers.base import LLMProvider, VisionLLMProvider
from src.providers.claude import ClaudeProvider
from src.providers.gemini import GeminiProvider
from src.providers.ollama import OllamaProvider, OllamaVisionProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    """設定値からLLMプロバイダーを生成する。

    Args:
        settings: LLMプロバイダー設定

    Returns:
        LLMProvider実装クラスのインスタンス

    Raises:
        ValueError: 未知のプロバイダー種別が指定された場合
    """
    match settings.llm_provider:
        case "ollama":
            return OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)
        case "claude":
            return ClaudeProvider(api_key=settings.anthropic_api_key)
        case "gemini":
            return GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
        case "azure_openai":
            return AzureOpenAIProvider(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def create_vision_provider(settings: Settings) -> VisionLLMProvider:
    """設定値からVisionプロバイダーを生成する。

    Args:
        settings: Visionプロバイダー設定

    Returns:
        VisionLLMProvider実装クラスのインスタンス

    Raises:
        ValueError: 未知のプロバイダー種別が指定された場合
    """
    match settings.llm_vision_provider:
        case "ollama":
            return OllamaVisionProvider(
                host=settings.ollama_host, vision_model=settings.ollama_vision_model
            )
        case "claude":
            return ClaudeProvider(api_key=settings.anthropic_api_key)
        case "gemini":
            return GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
        case "azure_openai":
            return AzureOpenAIProvider(
                api_key=settings.azure_openai_api_key,
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment,
            )
        case _:
            raise ValueError(f"Unknown vision provider: {settings.llm_vision_provider}")
