# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Install dependencies (once)
pip install -r requirements.txt

# Run
python main.py
```

The app requires a `.env` file with an Anthropic API key — copy `.env.example` to `.env` and fill it in. On Windows, run as Administrator if global hotkeys fail to register.

## Architecture

This is a single-process Windows desktop app. The threading model is the most important thing to understand:

- **Main thread** — runs the `customtkinter` / tkinter event loop (`root.mainloop()`). All UI mutations must happen here.
- **Hotkey callbacks** — fired by the `keyboard` library on its own thread. They must never touch UI directly; instead they call `self.root.after(0, fn)` to schedule work on the main thread.
- **AI calls** — run in daemon threads (`threading.Thread`) so they don't block the UI. Results are delivered back via `root.after(0, ...)`.
- **System tray** — `pystray` runs in its own daemon thread via `icon.run()`.

The `ScreenAssistant` class in `main.py` owns the entire app: hotkey registration, tray icon, and all UI windows.

## Key Files

| File | Responsibility |
|---|---|
| `main.py` | `ScreenAssistant` class — hotkeys, query popup, response panel, tray |
| `ai_engine.py` | `ask_claude()` — Claude Vision API call with agentic web_search tool loop |
| `screen_capture.py` | `capture()` — screenshot + cursor position, returns base64 PNG |
| `config.py` | Loads `ANTHROPIC_API_KEY`, `HOTKEY_INSTANT`, `HOTKEY_CUSTOM` from `.env` |

## Hotkeys

| Default | Env var | Behavior |
|---|---|---|
| `Ctrl+Shift+H` | `HOTKEY_INSTANT` | Capture → ask "What is this?" → show panel |
| `Ctrl+Shift+Q` | `HOTKEY_CUSTOM` | Capture → show text input popup → ask custom question → show panel |

Screenshot is always taken **before** any UI appears so the popup/panel is never included in the image sent to Claude.

## AI Engine (`ai_engine.py`)

`ask_claude()` runs an agentic tool-use loop:
1. Sends the base64 screenshot + cursor coords + question to `claude-sonnet-4-6`
2. If Claude responds with `stop_reason == "tool_use"`, executes the `web_search` tool via DuckDuckGo (top 3 results) and feeds results back
3. Loops until `stop_reason == "end_turn"`, then returns the text response

`duckduckgo-search` is an optional dependency — if not installed, web search degrades gracefully with an error string returned to Claude.

## UI Components (all in `main.py`)

- **Query popup** — `CTkToplevel` with `overrideredirect(True)` (no OS chrome), positioned 20px below/right of cursor, clamped to screen bounds. Capture happens before this appears.
- **Response panel** — `CTkToplevel` docked to the right edge of the screen, 440px wide, full screen height minus 80px. If the panel is already open when a new answer arrives, it updates in-place rather than spawning a new window. `_q_label` and `_answer_box` are stored as instance attributes for this update path.
- **Color palette** — Catppuccin Mocha constants defined at the top of `main.py` (`BG`, `SURFACE`, `ACCENT`, etc.).

## Changing the Model

The model is hardcoded as `"claude-sonnet-4-6"` in `ai_engine.py:75`. To swap it, change that string. The latest Claude model IDs: Opus 4.7 (`claude-opus-4-7`), Sonnet 4.6 (`claude-sonnet-4-6`), Haiku 4.5 (`claude-haiku-4-5-20251001`).
