import json
from pathlib import Path

CONFIG_FILE = Path(".queuectl_config.json")

BACKOFF_MAX_SECONDS = 60
WORKER_POLL_INTERVAL = 1

DEFAULT_CONFIG = {
    "max_retries": 3,
    "backoff_base": 2,
}

def get_config(key: str) -> str:
    if not CONFIG_FILE.exists():
        return str(DEFAULT_CONFIG.get(key, ""))
    
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        return str(data.get(key, DEFAULT_CONFIG.get(key, "")))

def set_config(key: str, value: str):
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    
    data[key] = value
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)
