import json
import pytest
from pathlib import Path
from unittest.mock import patch
from widget.config import load_config, save_config, Config, normalize_backend_url


def test_normalize_backend_url_adds_https_scheme():
    # スキーム欠落時は https:// を補完する（issue #36）
    assert normalize_backend_url("example.hf.space") == "https://example.hf.space"


def test_normalize_backend_url_strips_trailing_slash():
    assert normalize_backend_url("https://example.hf.space/") == "https://example.hf.space"


def test_normalize_backend_url_preserves_http_localhost():
    assert normalize_backend_url("http://localhost:8000") == "http://localhost:8000"


def test_normalize_backend_url_empty_stays_empty():
    assert normalize_backend_url("") == ""
    assert normalize_backend_url("   ") == ""


def test_load_config_creates_default_json_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        cfg = load_config()
    assert cfg.hotkey == "<ctrl>+<shift>+<space>"
    assert cfg.ollama_model == "qwen2.5:1.5b"
    assert cfg.backend_url == ""
    assert cfg.selected_user_id == ""
    assert config_path.exists()


def test_save_and_load_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        cfg = Config(backend_url="https://example.hf.space", selected_user_id="alice")
        save_config(cfg)
        loaded = load_config()
    assert loaded.backend_url == "https://example.hf.space"
    assert loaded.selected_user_id == "alice"


def test_load_config_ignores_unknown_keys(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"backend_url": "https://x.com", "unknown_key": "ignore_me"}))
    with patch("widget.config.CONFIG_PATH", config_path):
        cfg = load_config()
    assert cfg.backend_url == "https://x.com"


def test_first_run_complete_defaults_to_false(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        cfg = load_config()
    assert cfg.first_run_complete is False


def test_first_run_complete_persists(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        cfg = load_config()
        cfg.first_run_complete = True
        save_config(cfg)
        reloaded = load_config()
    assert reloaded.first_run_complete is True
