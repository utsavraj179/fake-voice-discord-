import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOKENS_FILE = BASE_DIR / "tokens.json"
CONFIG_FILE = BASE_DIR / "config.json"

def load_tokens():
    if not TOKENS_FILE.exists():
        return {}
    try:
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tokens(data):
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_config():
    env_user = os.environ.get("ADMIN_USER")
    env_pass = os.environ.get("ADMIN_PASS")
    if env_user and env_pass:
        return {"admin_user": env_user, "admin_pass": env_pass}

    if not CONFIG_FILE.exists():
        default_config = {
            "admin_user": "admin",
            "admin_pass": "admin123"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"admin_user": "admin", "admin_pass": "admin"}
