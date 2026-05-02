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

`screen_capture.py` draws a **hollow red ring** (radius 22px, with a 1px black halo on either side of the stroke for contrast on any background) at the cursor position before base64-encoding. This is the source of truth for "where the user is pointing" — vision models are weak at grounding raw pixel coordinates, and without a visible marker Claude tends to drift toward salient features (e.g. naming the taskbar when the cursor is mid-screen). The ring is hollow so the pixel directly under the cursor is never occluded. The `(x, y)` numbers are still passed in the text prompt as a hint, but the system prompt tells Claude to treat the ring as authoritative.

## AI Engine (`ai_engine.py`)

`ask_claude()` runs an agentic tool-use loop:
1. Sends the base64 screenshot + cursor coords + question to the model named in `ANTHROPIC_MODEL` (default `claude-haiku-4-5-20251001` — vision-capable and ~3× cheaper than Sonnet for this workload)
2. If Claude responds with `stop_reason == "tool_use"`, executes the `web_search` tool via DuckDuckGo (top 3 results) and feeds results back
3. Loops until `stop_reason == "end_turn"`, then returns the text response

`SYSTEM_PROMPT` instructs Claude to answer in **1–3 short sentences in plain everyday language** — no bullets, no numbered steps, no preamble. `max_tokens=400` is a hard ceiling that backs this up. Both are tuned to fit the small near-cursor answer popup; loosen them only if you also redesign the popup to handle long answers.

`duckduckgo-search` is an optional dependency — if not installed, web search degrades gracefully with an error string returned to Claude.

## UI Components (all in `main.py`)

Both popups use the same Apple-like rounded-bubble recipe:
- The outer `CTkToplevel` is `overrideredirect(True)` (no OS chrome), filled with the sentinel color `TRANSPARENT_KEY` (`#010101`), and that key is punched out via `wm_attributes("-transparentcolor", ...)` on Windows. The visible UI is an inner `CTkFrame` card with `corner_radius=18`, giving true rounded outer corners (no rectangular halo). `WIN_PAD=12` is the transparent margin around the card. The `wm_attributes` call is wrapped in try/except so non-Windows platforms degrade to square outer corners.

- **Query popup** (`_show_query_popup`) — `QUERY_POPUP_W` × `QUERY_POPUP_H` (420×142), positioned 20px below/right of cursor, clamped to screen bounds. Used only by the custom-question hotkey to take typed input.

- **Answer popup** (`_build_answer_popup` / `_show_or_update_answer_popup`) — **both dimensions auto-fit content** via `winfo_reqwidth()` / `winfo_reqheight()`. Width is clamped to `[ANSWER_POPUP_MIN_W=260, ANSWER_POPUP_MAX_W=380]` (the floor keeps the header — Assistant / Quit App / ✕ — from crowding; the ceiling matches the label `wraplength` so longer answers wrap inside the label and the popup caps at 380). Height is capped at `ANSWER_MAX_H_RATIO=0.60` of screen height. First show is anchored 20px below/right of the cursor position captured at hotkey time. Layout uses a 4-row grid where row 2 (the answer body) absorbs slack:
  - **Header row** — `Assistant` title on the left; `Quit App` button + round ✕ pill on the right. The header frame and title label are also the **drag handle** (bound to `<ButtonPress-1>` / `<B1-Motion>` → `_drag_start` / `_drag_motion`). Buttons keep their normal click behavior because tk button presses consume their own events.
  - **Question row** — muted, smaller font.
  - **Answer row** — `CTkLabel` with `wraplength` set so the label reflows; auto-fits height.
  - **Footer row** — `Copy` button on the right.
  - **`✕`** and **Esc** dismiss the popup. **`Quit App`** exits the entire app via `_quit_app()` — the tray menu's Quit item shares the same teardown.
  - If the popup is already open when a new answer arrives (e.g. `Thinking…` → final answer), `_show_or_update_answer_popup` updates the labels in place and calls `_fit_answer_popup(initial=False)` — this re-fits the height but **preserves the user's current top-left** (only clamping if the new height would push it off-screen), so a drag isn't undone.

- **Color palette** — Catppuccin Mocha constants at the top of `main.py` (`BG`, `SURFACE`, `ACCENT`, `DANGER`, etc.).
- **Typography** — `FONT_FAMILY_UI = "Segoe UI Variable Display"` / `FONT_FAMILY_BODY = "Segoe UI Variable Text"` (Win11-native; tk falls back silently if missing).

## Changing the Model

The model is read from `ANTHROPIC_MODEL` in `config.py` (default `claude-haiku-4-5-20251001`) and used in `ai_engine.py`'s `ask_claude()`. To swap it, set `ANTHROPIC_MODEL=...` in `.env`. The latest Claude model IDs: Opus 4.7 (`claude-opus-4-7`), Sonnet 4.6 (`claude-sonnet-4-6`), Haiku 4.5 (`claude-haiku-4-5-20251001`).
