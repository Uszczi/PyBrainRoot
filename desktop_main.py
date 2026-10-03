import os
import sys

# gładkie renderowanie tekstu na desktopie (antialiasing przez Pillow);
# zmienna musi być ustawiona PRZED pierwszym importem kivy
os.environ.setdefault("KIVY_TEXT", "pil")

# na natywnym Waylandzie okno ma fizyczne piksele (monitor HiDPI scale 2),
# a Kivy nie wykrywa gęstości — wymuszamy 2, żeby UI miało właściwą
# proporcję; nadpisz przez PYBRAINROOT_DENSITY (np. "1" na monitorze 1x).
# (KIVY_DPI nie działa: na Linuksie Kivy liczy gęstość z rozmiaru okna.)
if os.environ.get("SDL_VIDEODRIVER") == "wayland":
    os.environ.setdefault(
        "KIVY_METRICS_DENSITY", os.environ.get("PYBRAINROOT_DENSITY", "2")
    )

# _SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
# if _SRC_DIR not in sys.path:
#     sys.path.insert(0, _SRC_DIR)

from pybrainroot import desktop  # noqa: E402
from pybrainroot.app import main  # noqa: E402


def install_keyboard_demo() -> None:
    """Skróty 1-9/0 sterują symulowaną aplikacją na pierwszym planie."""
    from kivy.core.window import Window

    apps = desktop.FAKE_APPS

    def on_key(_window, _key, _scancode, codepoint, _modifiers):
        # w Kivy 2.3 pierwszym argumentem jest kod klawisza (int),
        # tekst znaku jest w codepoint
        if not codepoint:
            return False
        if codepoint == "0":
            desktop.go_home()
            return True
        if codepoint in "123456789":
            index = int(codepoint) - 1
            if index < len(apps):
                desktop.launch_app(apps[index][1])
            return True
        return False

    Window.bind(on_keyboard=on_key)


if __name__ == "__main__":
    from kivy.core.window import Window

    Window.size = (430, 820)

    desktop.apply_mocks()
    install_keyboard_demo()
    if not os.environ.get("PYBRAINROOT_NO_DEMO"):
        desktop.start_auto_demo()
    main()
