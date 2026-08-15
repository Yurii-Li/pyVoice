import os
import json
from pyvoice.utils.paths import get_project_root

CONFIG_FILENAME = "config.json"

def get_config_file_path() -> str:
    """Повертає шлях до config.json у кореневій папці"""
    return os.path.join(get_project_root(), CONFIG_FILENAME)

def load_app_config() -> dict:
    """Завантажує налаштування з config.json"""
    path = get_config_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_app_config(config_data: dict) -> None:
    """Зберігає налаштування у config.json"""
    path = get_config_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
