import os
from dotenv import load_dotenv

# override=True so .env always wins over any stale system env var
# (e.g. an old key from `setx` that's since been rotated).
load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HOTKEY_INSTANT = os.getenv("HOTKEY_INSTANT", "ctrl+shift+h")
HOTKEY_CUSTOM = os.getenv("HOTKEY_CUSTOM", "ctrl+shift+q")
