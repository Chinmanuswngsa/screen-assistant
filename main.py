"""
Screen Assistant — entry point.

Hotkeys (configurable in .env):
  Ctrl+Shift+H  →  instant "What is this?" answer
  Ctrl+Shift+Q  →  popup to type a custom question

Requires Python 3.11+ and an ANTHROPIC_API_KEY in a .env file.
Run with:  python main.py
On Windows, run as administrator if hotkeys don't register.
"""

import sys
import threading

import keyboard
import pystray
import customtkinter as ctk
from PIL import Image, ImageDraw

from config import ANTHROPIC_API_KEY, HOTKEY_INSTANT, HOTKEY_CUSTOM
from screen_capture import capture
from ai_engine import ask_claude

# Windows console defaults to cp1252; force UTF-8 so unicode prints don't crash.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── Palette ────────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
BG_DARK   = "#181825"
SURFACE   = "#313244"
MUTED     = "#45475a"
TEXT      = "#cdd6f4"
SUBTEXT   = "#a6adc8"
ACCENT    = "#89b4fa"
ACCENT2   = "#74c7ec"


class ScreenAssistant:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Hidden root window — keeps the tkinter event loop alive.
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root.title("Screen Assistant")

        self._answer_popup: ctk.CTkToplevel | None = None
        self._answer_q_label: ctk.CTkLabel | None = None
        self._answer_label: ctk.CTkLabel | None = None

        self._setup_tray()
        self._setup_hotkeys()

    # ── Hotkeys ────────────────────────────────────────────────────────────────

    def _setup_hotkeys(self):
        keyboard.add_hotkey(HOTKEY_INSTANT, self._on_instant)
        keyboard.add_hotkey(HOTKEY_CUSTOM,  self._on_custom)
        print(f"  {HOTKEY_INSTANT.upper()}  →  instant answer")
        print(f"  {HOTKEY_CUSTOM.upper()}  →  custom question")

    def _on_instant(self):
        b64, cx, cy, size = capture()
        question = "What is this?"
        self.root.after(0, lambda: self._show_or_update_answer_popup(question, "⏳ Thinking…", cx, cy))
        threading.Thread(
            target=self._ai_worker,
            args=(b64, cx, cy, size, question),
            daemon=True,
        ).start()

    def _on_custom(self):
        # Capture BEFORE the popup appears so the popup isn't in the screenshot.
        b64, cx, cy, size = capture()
        self.root.after(0, lambda: self._show_query_popup(b64, cx, cy, size))

    # ── Query popup ────────────────────────────────────────────────────────────

    def _show_query_popup(self, b64, cx, cy, size):
        popup = ctk.CTkToplevel(self.root)
        popup.title("")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(fg_color=BG)

        pw, ph = 390, 116
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        px = min(cx + 20, sw - pw - 10)
        py = min(cy + 20, sh - ph - 10)
        popup.geometry(f"{pw}x{ph}+{px}+{py}")

        ctk.CTkLabel(
            popup, text="🤖  Ask AI Assistant",
            font=("Segoe UI", 13, "bold"), text_color=TEXT,
        ).pack(pady=(10, 4), padx=14, anchor="w")

        entry = ctk.CTkEntry(
            popup, width=362, font=("Segoe UI", 12),
            fg_color=SURFACE, border_color=MUTED, text_color=TEXT,
        )
        entry.pack(padx=14)
        entry.insert(0, "What is this?")
        entry.select_range(0, "end")
        entry.focus_force()

        btn_row = ctk.CTkFrame(popup, fg_color="transparent")
        btn_row.pack(pady=8, padx=14, anchor="e")

        def submit():
            q = entry.get().strip() or "What is this?"
            popup.destroy()
            self._show_or_update_answer_popup(q, "⏳ Thinking…", cx, cy)
            threading.Thread(
                target=self._ai_worker,
                args=(b64, cx, cy, size, q),
                daemon=True,
            ).start()

        ctk.CTkButton(
            btn_row, text="Cancel", width=82,
            fg_color=MUTED, hover_color=SURFACE, text_color=TEXT,
            command=popup.destroy,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Ask ↵", width=82,
            fg_color=ACCENT, hover_color=ACCENT2, text_color=BG,
            command=submit,
        ).pack(side="left")

        popup.bind("<Return>", lambda _: submit())
        popup.bind("<Escape>", lambda _: popup.destroy())

    # ── AI worker (background thread) ─────────────────────────────────────────

    def _ai_worker(self, b64, cx, cy, size, question):
        sw, sh = size
        try:
            answer = ask_claude(b64, cx, cy, sw, sh, question)
        except Exception as exc:
            answer = f"Error: {exc}"
        self.root.after(0, lambda: self._show_or_update_answer_popup(question, answer, cx, cy))

    # ── Answer popup (small, near-cursor) ─────────────────────────────────────

    def _show_or_update_answer_popup(self, question: str, answer: str,
                                     anchor_x: int, anchor_y: int):
        if self._answer_popup and self._answer_popup.winfo_exists():
            self._answer_q_label.configure(text=question)
            self._answer_label.configure(text=answer)
            self._reposition_answer_popup(anchor_x, anchor_y)
        else:
            self._build_answer_popup(question, answer, anchor_x, anchor_y)

    def _build_answer_popup(self, question: str, answer: str,
                            anchor_x: int, anchor_y: int):
        popup = ctk.CTkToplevel(self.root)
        popup.title("")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(fg_color=BG)
        self._answer_popup = popup

        # Header row: bot mark on the left; quit + close on the right.
        # Pack ✕ first so it's the rightmost; Quit packs to its left.
        hdr = ctk.CTkFrame(popup, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            hdr, text="🤖", text_color=ACCENT,
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="✕", width=22, height=22,
            fg_color="transparent", hover_color=MUTED, text_color=SUBTEXT,
            command=popup.destroy,
        ).pack(side="right")
        ctk.CTkButton(
            hdr, text="Quit", width=44, height=22,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color="#7d2f2f", text_color=SUBTEXT,
            command=self._quit_app,
        ).pack(side="right", padx=(0, 4))

        # Question — small, italic, muted
        self._answer_q_label = ctk.CTkLabel(
            popup, text=question,
            font=("Segoe UI", 10, "italic"), text_color=SUBTEXT,
            wraplength=350, justify="left", anchor="w",
        )
        self._answer_q_label.pack(fill="x", padx=14, pady=(0, 4))

        # Answer — main body
        self._answer_label = ctk.CTkLabel(
            popup, text=answer,
            font=("Segoe UI", 12), text_color=TEXT,
            wraplength=350, justify="left", anchor="w",
        )
        self._answer_label.pack(fill="x", padx=14, pady=(0, 8))

        # Footer: copy button (right-aligned)
        def copy_answer():
            popup.clipboard_clear()
            popup.clipboard_append(self._answer_label.cget("text"))

        ftr = ctk.CTkFrame(popup, fg_color="transparent")
        ftr.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkButton(
            ftr, text="📋  Copy", width=78, height=24,
            font=("Segoe UI", 10),
            fg_color=SURFACE, hover_color=MUTED, text_color=TEXT,
            command=copy_answer,
        ).pack(side="right")

        popup.bind("<Escape>", lambda _: popup.destroy())

        self._reposition_answer_popup(anchor_x, anchor_y)
        popup.focus_force()

    def _reposition_answer_popup(self, anchor_x: int, anchor_y: int):
        popup = self._answer_popup
        popup.update_idletasks()
        pw = max(380, popup.winfo_reqwidth())
        ph = popup.winfo_reqheight()
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        px = min(max(anchor_x + 20, 10), sw - pw - 10)
        py = min(max(anchor_y + 20, 10), sh - ph - 10)
        popup.geometry(f"{pw}x{ph}+{px}+{py}")

    # ── System tray ────────────────────────────────────────────────────────────

    def _setup_tray(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill="#89b4fa")
        draw.ellipse([16, 16, 48, 48], fill="#1e1e2e")

        self._tray = pystray.Icon(
            "ScreenAssistant",
            img,
            f"Screen Assistant\n{HOTKEY_INSTANT.upper()}: instant\n{HOTKEY_CUSTOM.upper()}: ask",
            menu=pystray.Menu(pystray.MenuItem("Quit", lambda _icon, _item: self._quit_app())),
        )
        threading.Thread(target=self._tray.run, daemon=True).start()

    # ── Quit ───────────────────────────────────────────────────────────────────

    def _quit_app(self):
        keyboard.unhook_all_hotkeys()
        if self._tray:
            self._tray.stop()
        self.root.after(0, self.root.destroy)

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self):
        print("Screen Assistant is running. Check the system tray.")
        self.root.mainloop()


def main():
    if not ANTHROPIC_API_KEY:
        print(
            "ERROR: ANTHROPIC_API_KEY is not set.\n"
            "Create a file named '.env' in this folder with:\n\n"
            "  ANTHROPIC_API_KEY=your_key_here\n"
        )
        sys.exit(1)

    app = ScreenAssistant()
    app.run()


if __name__ == "__main__":
    main()
