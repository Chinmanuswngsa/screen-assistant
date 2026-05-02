import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HOTKEY_INSTANT = os.getenv("HOTKEY_INSTANT", "ctrl+shift+h")
HOTKEY_CUSTOM = os.getenv("HOTKEY_CUSTOM", "ctrl+shift+q")
