from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class Config:
    backend_url: str = ""
    frontend_url: str = ""
    selected_user_id: str = ""
    hotkey: str = "<ctrl>+<shift>+<space>"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_vision_model: str = "gemma4:e4b"
    vision_provider: str = "local"   # "local" | "google"
    google_api_key: str = ""
    first_run_complete: bool = False


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return Config()
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})


def save_config(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
