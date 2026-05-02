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
DANGER    = "#f38ba8"

# ── Typography ─────────────────────────────────────────────────────────────────
# Segoe UI Variable Display/Text are present on Windows 11; tk falls back
# silently if missing. Centralized so the whole app shares one type scale.
FONT_FAMILY_UI   = "Segoe UI Variable Display"
FONT_FAMILY_BODY = "Segoe UI Variable Text"

# ── Popup geometry ─────────────────────────────────────────────────────────────
# Width is dynamic: popup shrinks to fit short answers, grows up to MAX_W for
# longer ones, with MIN_W keeping the header (Assistant / Quit App / ✕) from
# crowding. Height always fits content, capped at MAX_H_RATIO of screen height.
ANSWER_POPUP_MAX_W   = 380
ANSWER_POPUP_MIN_W   = 260
ANSWER_MAX_H_RATIO   = 0.60
QUERY_POPUP_W        = 420
QUERY_POPUP_H        = 142
WIN_PAD              = 12    # transparent margin around each card (room for shadow + rounded corners)

# Sentinel color used as the Windows -transparentcolor key. The outer Toplevel
# is filled with this color, then made transparent via wm_attributes, leaving
# only the rounded inner card visible — that's how we get true rounded outer
# corners (Apple-like) on a tkinter borderless window. Picked to be distinct
# from every other color in the palette so it never accidentally appears in a
# rendered widget.
TRANSPARENT_KEY = "#010101"


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
        self._answer_anchor: tuple[int, int] = (0, 0)
        self._drag_dx: int = 0
        self._drag_dy: int = 0

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
        self.root.after(0, lambda: self._show_or_update_answer_popup(question, "Thinking…", cx, cy))
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
        popup.configure(fg_color=TRANSPARENT_KEY)
        try:
            popup.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            pass

        pw, ph = QUERY_POPUP_W, QUERY_POPUP_H
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        px = min(cx + 20, sw - pw - 10)
        py = min(cy + 20, sh - ph - 10)
        popup.geometry(f"{pw}x{ph}+{px}+{py}")

        card = ctk.CTkFrame(
            popup, fg_color=BG, border_width=1,
            border_color=SURFACE, corner_radius=18,
        )
        card.pack(fill="both", expand=True, padx=WIN_PAD, pady=WIN_PAD)

        ctk.CTkLabel(
            card, text="Ask AI Assistant",
            font=(FONT_FAMILY_UI, 13, "bold"), text_color=TEXT,
        ).pack(pady=(14, 8), padx=18, anchor="w")

        entry = ctk.CTkEntry(
            card, height=34, font=(FONT_FAMILY_BODY, 12),
            fg_color=SURFACE, border_color=MUTED, border_width=1,
            text_color=TEXT, corner_radius=10,
        )
        entry.pack(fill="x", padx=18)
        entry.insert(0, "What is this?")
        entry.select_range(0, "end")
        entry.focus_force()

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(12, 14), padx=18, anchor="e")

        def submit():
            q = entry.get().strip() or "What is this?"
            popup.destroy()
            self._show_or_update_answer_popup(q, "Thinking…", cx, cy)
            threading.Thread(
                target=self._ai_worker,
                args=(b64, cx, cy, size, q),
                daemon=True,
            ).start()

        ctk.CTkButton(
            btn_row, text="Cancel", width=82, height=28,
            font=(FONT_FAMILY_UI, 11),
            fg_color="transparent", hover_color=SURFACE,
            text_color=SUBTEXT, border_width=0, corner_radius=14,
            command=popup.destroy,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Ask  ↵", width=82, height=28,
            font=(FONT_FAMILY_UI, 11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT2, text_color=BG_DARK,
            corner_radius=14,
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
            # Resize to fit the new content but keep the user's current top-left
            # (they may have dragged the popup since it appeared).
            self._fit_answer_popup(initial=False)
        else:
            self._build_answer_popup(question, answer, anchor_x, anchor_y)

    def _build_answer_popup(self, question: str, answer: str,
                            anchor_x: int, anchor_y: int):
        popup = ctk.CTkToplevel(self.root)
        popup.title("")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        # Outer fill is the transparent key; wm_attributes punches it out so
        # only the rounded card is visible — no rectangular halo around it.
        popup.configure(fg_color=TRANSPARENT_KEY)
        try:
            popup.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            pass  # non-Windows or unsupported; popup will just have square outer corners
        self._answer_popup = popup
        self._answer_anchor = (anchor_x, anchor_y)

        # Rounded "bubble" card — Apple-style large radius, soft border.
        card = ctk.CTkFrame(
            popup, fg_color=BG, border_width=1,
            border_color=SURFACE, corner_radius=18,
        )
        card.pack(fill="both", expand=True, padx=WIN_PAD, pady=WIN_PAD)

        # Grid so the answer row absorbs slack on resize; header/footer stay put.
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=0)
        card.grid_rowconfigure(1, weight=0)
        card.grid_rowconfigure(2, weight=1)
        card.grid_rowconfigure(3, weight=0)

        # — Header (also the drag handle)
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))

        title = ctk.CTkLabel(
            hdr, text="Assistant",
            font=(FONT_FAMILY_UI, 13, "bold"), text_color=TEXT,
        )
        title.pack(side="left")

        # Close (just the popup) — round pill, prominent on hover.
        ctk.CTkButton(
            hdr, text="✕", width=28, height=28,
            font=(FONT_FAMILY_UI, 13, "bold"),
            fg_color=SURFACE, hover_color=DANGER,
            text_color=TEXT, corner_radius=14,
            command=popup.destroy,
        ).pack(side="right")

        # Quit (the whole app) — labelled clearly so it isn't confused with ✕.
        ctk.CTkButton(
            hdr, text="Quit App", width=70, height=28,
            font=(FONT_FAMILY_UI, 10),
            fg_color="transparent", hover_color=SURFACE,
            text_color=SUBTEXT, corner_radius=14,
            command=self._quit_app,
        ).pack(side="right", padx=(0, 6))

        # Drag-to-move: bind on the header frame and the title label only,
        # so clicks on the buttons keep their normal behavior.
        for w in (hdr, title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_motion)

        wrap = ANSWER_POPUP_MAX_W - 2 * WIN_PAD - 36

        # — Question (italic-feel via muted color + smaller body font)
        self._answer_q_label = ctk.CTkLabel(
            card, text=question,
            font=(FONT_FAMILY_BODY, 11), text_color=SUBTEXT,
            anchor="w", justify="left",
            wraplength=wrap,
        )
        self._answer_q_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        # — Answer body. Plain label so the popup auto-sizes to content; if
        # content somehow exceeds the height cap, it'll clip rather than
        # scroll (acceptable given the system prompt forces ≤3 sentences).
        self._answer_label = ctk.CTkLabel(
            card, text=answer,
            font=(FONT_FAMILY_BODY, 12), text_color=TEXT,
            anchor="nw", justify="left",
            wraplength=wrap,
        )
        self._answer_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))

        # — Footer
        def copy_answer():
            popup.clipboard_clear()
            popup.clipboard_append(self._answer_label.cget("text"))

        ftr = ctk.CTkFrame(card, fg_color="transparent")
        ftr.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        ctk.CTkButton(
            ftr, text="Copy", width=72, height=28,
            font=(FONT_FAMILY_UI, 10, "bold"),
            fg_color=SURFACE, hover_color=MUTED, text_color=TEXT,
            corner_radius=14,
            command=copy_answer,
        ).pack(side="right")

        popup.bind("<Escape>", lambda _: popup.destroy())
        self._fit_answer_popup(initial=True)
        popup.focus_force()

    # ── Sizing & dragging helpers ─────────────────────────────────────────────

    def _fit_answer_popup(self, initial: bool):
        """Size the popup to its content in *both* dimensions.

        Width shrinks for short answers and grows up to MAX_W for longer ones
        (longer than that and content wraps inside the label, so width caps).
        Height fits content, capped at a fraction of screen height.

        On initial show, anchor near the cursor. On subsequent updates (e.g.
        Thinking… → final answer), keep the user's current top-left so a drag
        isn't undone — only clamp if the new size would push it off-screen.
        """
        popup = self._answer_popup
        popup.update_idletasks()
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()

        needed_w = popup.winfo_reqwidth()
        needed_h = popup.winfo_reqheight()
        w = max(ANSWER_POPUP_MIN_W, min(needed_w, ANSWER_POPUP_MAX_W))
        h = min(needed_h, int(sh * ANSWER_MAX_H_RATIO))

        if initial:
            ax, ay = self._answer_anchor
            px = min(max(ax + 20, 10), sw - w - 10)
            py = min(max(ay + 20, 10), sh - h - 10)
        else:
            px = max(10, min(popup.winfo_x(), sw - w - 10))
            py = max(10, min(popup.winfo_y(), sh - h - 10))

        popup.geometry(f"{w}x{h}+{px}+{py}")

    def _drag_start(self, event):
        popup = self._answer_popup
        if not popup:
            return
        self._drag_dx = event.x_root - popup.winfo_x()
        self._drag_dy = event.y_root - popup.winfo_y()

    def _drag_motion(self, event):
        popup = self._answer_popup
        if not popup:
            return
        nx = event.x_root - self._drag_dx
        ny = event.y_root - self._drag_dy
        popup.geometry(f"+{nx}+{ny}")

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
