from langfuse import Langfuse

from src.models.config import Settings


def get_langfuse_client(settings: Settings) -> Langfuse | None:
    if not settings.langfuse_secret_key or not settings.langfuse_public_key:
        return None
    return Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )
