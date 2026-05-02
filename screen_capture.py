import io
import base64
import pyautogui
from PIL import ImageGrab, ImageDraw

# Hollow-ring cursor marker. Vision models are weak at grounding raw pixel
# coordinates, so we draw the cursor position visibly on the image instead of
# relying on Claude to mentally divide the screen into a coordinate grid.
# A *hollow* ring (rather than a filled dot) is used so the pixel directly
# under the cursor is never occluded.
MARKER_RADIUS = 22       # outer radius of the red ring
MARKER_STROKE = 3        # thickness of the red ring
MARKER_HALO   = 1        # thin black outline either side of the red ring
MARKER_RED    = (255, 59, 48, 255)
MARKER_BLACK  = (0, 0, 0, 255)


def _draw_cursor_marker(img, x: int, y: int):
    draw = ImageDraw.Draw(img)
    r_outer = MARKER_RADIUS
    r_inner = MARKER_RADIUS - MARKER_STROKE
    # Black halo on the outside and inside of the red ring so it stays visible
    # against any background color.
    draw.ellipse(
        (x - r_outer - MARKER_HALO, y - r_outer - MARKER_HALO,
         x + r_outer + MARKER_HALO, y + r_outer + MARKER_HALO),
        outline=MARKER_BLACK, width=MARKER_HALO,
    )
    draw.ellipse(
        (x - r_outer, y - r_outer, x + r_outer, y + r_outer),
        outline=MARKER_RED, width=MARKER_STROKE,
    )
    draw.ellipse(
        (x - r_inner, y - r_inner, x + r_inner, y + r_inner),
        outline=MARKER_BLACK, width=MARKER_HALO,
    )


def capture():
    """Return (b64_png, cursor_x, cursor_y, (screen_w, screen_h))."""
    x, y = pyautogui.position()
    screenshot = ImageGrab.grab(all_screens=True)
    _draw_cursor_marker(screenshot, x, y)
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return b64, x, y, screenshot.size
