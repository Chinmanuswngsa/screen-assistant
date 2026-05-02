# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Install dependencies (once)
pip install -r requirements.txt

# Run
python main.py
```

The app needs `ANTHROPIC_API_KEY`. `config.py` calls `load_dotenv(override=True)`, so **`.env` always wins** over any value already in the system environment. This is deliberate — it means rotating the key is just "edit `.env`", with no need to fight a stale `setx` value.

- **`.env` file (preferred):** create `.env` next to `main.py` containing `ANTHROPIC_API_KEY=sk-ant-...`. `.env` is gitignored.
- **System env var (fallback):** if `.env` is absent or doesn't define the key, `os.getenv("ANTHROPIC_API_KEY")` is used instead. `setx ANTHROPIC_API_KEY "sk-ant-..."` works for that path; restart the terminal after setting.

On Windows, run as Administrator if global hotkeys fail to register.

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
| `main.py` | `ScreenAssistant` class — hotkeys, query popup, answer popup, tray |
| `ai_engine.py` | `ask_claude()` — Claude Vision API call with agentic web_search tool loop |
| `screen_capture.py` | `capture()` — screenshot + cursor position, returns base64 PNG |
| `config.py` | Loads `ANTHROPIC_API_KEY`, `HOTKEY_INSTANT`, `HOTKEY_CUSTOM` from env / `.env` |

## Hotkeys

| Default | Env var | Behavior |
|---|---|---|
| `Ctrl+Shift+H` | `HOTKEY_INSTANT` | Capture → ask "What is this?" → show answer popup at cursor |
| `Ctrl+Shift+Q` | `HOTKEY_CUSTOM` | Capture → input popup → custom question → answer popup at cursor |

Screenshot is always taken **before** any UI appears so the popup is never included in the image sent to Claude. The cursor `(cx, cy)` captured at hotkey-press time is threaded through `_ai_worker` so the answer popup can anchor at the original cursor position even if the user has since moved the mouse.

## AI Engine (`ai_engine.py`)

`ask_claude()` runs an agentic tool-use loop:
1. Sends the base64 screenshot + cursor coords + question to `claude-sonnet-4-6`
2. If Claude responds with `stop_reason == "tool_use"`, executes the `web_search` tool via DuckDuckGo (top 3 results) and feeds results back
3. Loops until `stop_reason == "end_turn"`, then returns the text response

`SYSTEM_PROMPT` instructs Claude to answer in **1–3 short sentences in plain everyday language** — no bullets, no numbered steps, no preamble. `max_tokens=400` is a hard ceiling that backs this up. Both are tuned to fit the small near-cursor answer popup; loosen them only if you also redesign the popup to handle long answers.

`duckduckgo-search` is an optional dependency — if not installed, web search degrades gracefully with an error string returned to Claude.

## UI Components (all in `main.py`)

- **Query popup** (`_show_query_popup`) — `CTkToplevel` with `overrideredirect(True)` (no OS chrome), 390×116, positioned 20px below/right of cursor, clamped to screen bounds. Used only by the custom-question hotkey to take typed input.
- **Answer popup** (`_build_answer_popup` / `_show_or_update_answer_popup`) — small near-cursor `CTkToplevel`, also `overrideredirect(True)`, min width 380px, **height auto-sized** to content via `winfo_reqheight()`. Anchored 20px below/right of the cursor position captured at hotkey time, clamped to screen. Layout: header row (🤖 left; `Quit` + `✕` right), italic muted question label, main answer label, footer Copy button. `✕` and Esc dismiss the popup; **`Quit` exits the entire app** via `_quit_app()` (also wired to the tray menu's Quit item, so both paths share the same teardown). If the popup is already open when a new answer arrives, it updates in-place via `configure(text=...)` and re-clamps geometry — `_answer_q_label` and `_answer_label` are stored as instance attributes for this path. **There is no longer a docked right-side panel.**
- **Color palette** — Catppuccin Mocha constants defined at the top of `main.py` (`BG`, `SURFACE`, `ACCENT`, etc.).

## Changing the Model

The model is hardcoded as `"claude-sonnet-4-6"` in `ai_engine.py:77`. To swap it, change that string. The latest Claude model IDs: Opus 4.7 (`claude-opus-4-7`), Sonnet 4.6 (`claude-sonnet-4-6`), Haiku 4.5 (`claude-haiku-4-5-20251001`).
