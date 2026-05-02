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
import webbrowser

import keyboard
import pystray
import customtkinter as ctk
from PIL import Image, ImageDraw

from config import ANTHROPIC_API_KEY, HOTKEY_INSTANT, HOTKEY_CUSTOM
from screen_capture import capture
from ai_engine import ask_claude


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

        self._panel: ctk.CTkToplevel | None = None
        self._q_label: ctk.CTkLabel | None = None
        self._answer_box: ctk.CTkTextbox | None = None
        self._last_question: str = ""

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
        self.root.after(0, lambda: self._show_or_update_panel(question, "⏳ Thinking…"))
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
            self._show_or_update_panel(q, "⏳ Thinking…")
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
        self.root.after(0, lambda: self._show_or_update_panel(question, answer))

    # ── Response panel ─────────────────────────────────────────────────────────

    def _show_or_update_panel(self, question: str, answer: str):
        self._last_question = question
        if self._panel and self._panel.winfo_exists():
            self._q_label.configure(text=f"Q: {question}")
            self._answer_box.configure(state="normal")
            self._answer_box.delete("1.0", "end")
            self._answer_box.insert("1.0", answer)
            self._answer_box.configure(state="disabled")
        else:
            self._build_panel(question, answer)

    def _build_panel(self, question: str, answer: str):
        panel = ctk.CTkToplevel(self.root)
        panel.title("AI Assistant")
        panel.attributes("-topmost", True)
        panel.configure(fg_color=BG)
        self._panel = panel

        sw = panel.winfo_screenwidth()
        sh = panel.winfo_screenheight()
        pw = 440
        ph = sh - 80
        panel.geometry(f"{pw}x{ph}+{sw - pw - 12}+40")
        panel.resizable(False, True)
        panel.minsize(pw, 300)

        # Header
        hdr = ctk.CTkFrame(panel, fg_color=BG_DARK, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr, text="🤖  AI Assistant",
            font=("Segoe UI", 14, "bold"), text_color=TEXT,
        ).pack(side="left", padx=14, pady=10)
        ctk.CTkButton(
            hdr, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=MUTED, text_color=SUBTEXT,
            command=panel.destroy,
        ).pack(side="right", padx=8, pady=6)

        # Question label
        self._q_label = ctk.CTkLabel(
            panel, text=f"Q: {question}",
            font=("Segoe UI", 11, "italic"), text_color=SUBTEXT,
            wraplength=400, justify="left",
        )
        self._q_label.pack(padx=14, pady=(10, 4), anchor="w")

        ctk.CTkFrame(panel, height=1, fg_color=SURFACE).pack(fill="x", padx=14)

        # Answer textbox
        self._answer_box = ctk.CTkTextbox(
            panel,
            font=("Segoe UI", 12), fg_color=BG_DARK,
            text_color=TEXT, wrap="word", border_width=0,
        )
        self._answer_box.pack(fill="both", expand=True, padx=14, pady=10)
        self._answer_box.insert("1.0", answer)
        self._answer_box.configure(state="disabled")

        # Footer buttons
        ftr = ctk.CTkFrame(panel, fg_color=BG_DARK, corner_radius=0)
        ftr.pack(fill="x")

        def copy_answer():
            text = self._answer_box.get("1.0", "end").strip()
            panel.clipboard_clear()
            panel.clipboard_append(text)

        def search_docs():
            q = self._last_question.replace(" ", "+")
            webbrowser.open(f"https://www.google.com/search?q={q}")

        ctk.CTkButton(
            ftr, text="📋  Copy", width=120,
            fg_color=SURFACE, hover_color=MUTED, text_color=TEXT,
            command=copy_answer,
        ).pack(side="left", padx=10, pady=8)
        ctk.CTkButton(
            ftr, text="🔍  Search docs", width=150,
            fg_color=SURFACE, hover_color=MUTED, text_color=TEXT,
            command=search_docs,
        ).pack(side="left", padx=(0, 10), pady=8)

        panel.bind("<Escape>", lambda _: panel.destroy())

    # ── System tray ────────────────────────────────────────────────────────────

    def _setup_tray(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill="#89b4fa")
        draw.ellipse([16, 16, 48, 48], fill="#1e1e2e")

        def quit_app(icon, _item):
            keyboard.unhook_all_hotkeys()
            icon.stop()
            self.root.after(0, self.root.destroy)

        self._tray = pystray.Icon(
            "ScreenAssistant",
            img,
            f"Screen Assistant\n{HOTKEY_INSTANT.upper()}: instant\n{HOTKEY_CUSTOM.upper()}: ask",
            menu=pystray.Menu(pystray.MenuItem("Quit", quit_app)),
        )
        threading.Thread(target=self._tray.run, daemon=True).start()

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
