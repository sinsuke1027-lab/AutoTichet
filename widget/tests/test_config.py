import json
import pytest
from pathlib import Path
from unittest.mock import patch


def test_load_config_creates_default_json_when_missing(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config, Config
        cfg = load_config()
    assert cfg.hotkey == "<ctrl>+<shift>+<space>"
    assert cfg.ollama_model == "gemma4:e4b"
    assert cfg.backend_url == ""
    assert cfg.selected_user_id == ""
    assert config_path.exists()


def test_save_and_load_roundtrip(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config, save_config, Config
        cfg = Config(backend_url="https://example.hf.space", selected_user_id="alice")
        save_config(cfg)
        loaded = load_config()
    assert loaded.backend_url == "https://example.hf.space"
    assert loaded.selected_user_id == "alice"


def test_load_config_ignores_unknown_keys(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"backend_url": "https://x.com", "unknown_key": "ignore_me"}))
    with patch("widget.config.CONFIG_PATH", config_path):
        from widget.config import load_config
        cfg = load_config()
    assert cfg.backend_url == "https://x.com"
