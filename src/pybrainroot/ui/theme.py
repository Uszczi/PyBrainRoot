"""Ciemny motyw aplikacji — paleta i fabryki widżetów.

Kolory są spójne z nakładką systemową (android_overlay.py), dzięki czemu
modal wygląda jak część tej samej aplikacji.
"""
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

# ---------------------------------------------------------------- paleta

BACKGROUND = (0.07, 0.08, 0.10, 1)  # tło okna
SURFACE = (0.11, 0.13, 0.16, 1)  # karty, pola tekstowe
PRIMARY = (0.24, 0.44, 0.71, 1)  # akcent (#3D6FB4)
TEXT = (0.92, 0.94, 0.97, 1)  # tekst główny
SUBTLE = (0.55, 0.59, 0.68, 1)  # tekst pomocniczy
DANGER = (0.66, 0.27, 0.27, 1)  # guzik „zamknij aplikację”

# wersje szesnastkowe do markupy Kivy ([color=...])
TEXT_HEX = "E8ECF4"
SUBTLE_HEX = "8A93A6"


def _dim(color: tuple, factor: float) -> tuple:
    """Przyciemnia kolor (bez zmiany alfy)."""
    return (*[c * factor for c in color[:3]], color[3])


def _scale(kwargs: dict) -> None:
    """Wymiary widżetu podajemy w „dp” — tu konwertujemy na piksele.

    Dzięki temu UI skaluje się z gęstością: 1× na zwykłym desktopie,
    2× na Waylandzie z HiDPI i 3× na telefonie.
    """
    for key in ("height", "width"):
        if kwargs.get(key) is not None:
            kwargs[key] = dp(kwargs[key])


# ------------------------------------------------------------- widżety

def label(
    text: str,
    *,
    bold: bool = False,
    color: tuple = TEXT,
    font_size: str = "16sp",
    halign: str = "left",
    valign: str = "middle",
    **kwargs,
) -> Label:
    """Etykieta w kolorach motywu."""
    _scale(kwargs)
    return Label(
        text=text,
        bold=bold,
        color=color,
        font_size=font_size,
        halign=halign,
        valign=valign,
        **kwargs,
    )


def button(
    text: str,
    on_press=None,
    *,
    height: int = 60,
    color: tuple = PRIMARY,
    text_color: tuple = TEXT,
    font_size: str = "17sp",
    **kwargs,
) -> Button:
    """Płaski guzik — po wciśnięciu robi się ciemniejszy."""
    _scale(kwargs)
    height = dp(height)
    btn = Button(
        text=text,
        size_hint_y=None,
        height=height,
        font_size=font_size,
        background_normal="",
        background_down="",
        background_color=color,
        color=text_color,
        **kwargs,
    )

    def _on_state(_btn, state) -> None:
        btn.background_color = _dim(color, 0.82 if state == "down" else 1.0)

    btn.bind(state=_on_state)
    if on_press is not None:
        btn.bind(on_press=lambda _i: on_press())
    return btn


def text_input(hint: str = "", **kwargs) -> TextInput:
    """Pole tekstowe w kolorach motywu."""
    kwargs.setdefault("height", 52)
    _scale(kwargs)
    height = kwargs.pop("height")
    return TextInput(
        hint_text=hint,
        multiline=False,
        size_hint_y=None,
        height=height,
        font_size="16sp",
        padding=(12, 12),
        background_normal="",
        background_active="",
        background_color=SURFACE,
        foreground_color=TEXT,
        hint_text_color=SUBTLE,
        cursor_color=(*TEXT[:3], 1),
        **kwargs,
    )


def checkbox(**kwargs) -> CheckBox:
    """Checkbox — zmienia kolor po zaznaczeniu."""
    _scale(kwargs)
    cb = CheckBox(color=TEXT, **kwargs)

    def _on_active(_cb, active) -> None:
        cb.color = PRIMARY if active else TEXT

    cb.bind(active=_on_active)
    return cb
