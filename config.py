import os
from dotenv import load_dotenv

# override=True so .env always wins over any stale system env var
# (e.g. an old key from `setx` that's since been rotated).
load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HOTKEY_INSTANT = os.getenv("HOTKEY_INSTANT", "ctrl+shift+h")
HOTKEY_CUSTOM = os.getenv("HOTKEY_CUSTOM", "ctrl+shift+q")

# Default to Haiku 4.5 — has vision, ~3x cheaper than Sonnet for this workload.
# Override via ANTHROPIC_MODEL in .env (e.g. claude-sonnet-4-6 for higher quality).
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
