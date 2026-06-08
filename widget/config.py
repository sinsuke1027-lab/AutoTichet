from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class Config:
    backend_url: str = ""
    selected_user_id: str = ""
    hotkey: str = "<ctrl>+<shift>+<space>"
    ollama_model: str = "gemma4:e4b"


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    with CONFIG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})


def save_config(cfg: Config) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
