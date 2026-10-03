"""Treść modala Kivy — fallback, gdy nakładka systemowa jest niedostępna."""

from kivy.uix.boxlayout import BoxLayout

from pybrainroot.ui import theme


def build_modal_content(message: str, on_close=None) -> BoxLayout:
    """Buduje zawartość popupu.

    Gdy podano `on_close`, modal dostaje guzik „Zamknij aplikację”,
    który wywołuje `on_close` (a nie tylko chowa popup).
    """
    content = BoxLayout(orientation="vertical", padding=16, spacing=12)
    content.add_widget(
        theme.label(message, halign="center", valign="middle", font_size="17sp")
    )
    if on_close:
        close_btn = theme.button(
            "✖ Zamknij aplikację",
            on_close,
            height=52,
            color=theme.DANGER,
        )
        content.add_widget(close_btn)
    return content
