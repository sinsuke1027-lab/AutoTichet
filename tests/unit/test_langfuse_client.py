from unittest.mock import MagicMock, patch

from src.models.config import Settings
from src.services.langfuse_client import get_langfuse_client


def _settings_with_keys() -> Settings:
    return Settings(
        langfuse_secret_key="sk-lf-test",
        langfuse_public_key="pk-lf-test",
        langfuse_host="http://localhost:3000",
    )


def _settings_without_keys() -> Settings:
    return Settings(langfuse_secret_key="", langfuse_public_key="")


def test_get_langfuse_client_returns_none_when_keys_missing() -> None:
    assert get_langfuse_client(_settings_without_keys()) is None


def test_get_langfuse_client_returns_none_when_secret_key_only() -> None:
    settings = Settings(langfuse_secret_key="sk-lf-test", langfuse_public_key="")
    assert get_langfuse_client(settings) is None


def test_get_langfuse_client_returns_instance_when_configured() -> None:
    with patch("src.services.langfuse_client.Langfuse") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = get_langfuse_client(_settings_with_keys())
    assert client is not None
    mock_cls.assert_called_once_with(
        secret_key="sk-lf-test",
        public_key="pk-lf-test",
        host="http://localhost:3000",
    )
