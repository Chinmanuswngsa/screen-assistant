import io
import base64
import pyautogui
from PIL import ImageGrab


def capture():
    """Return (b64_png, cursor_x, cursor_y, (screen_w, screen_h))."""
    x, y = pyautogui.position()
    screenshot = ImageGrab.grab(all_screens=True)
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, x, y, screenshot.size
