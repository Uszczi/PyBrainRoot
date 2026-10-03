"""Aplikacja Kivy: punkt wejścia i zgoda na powiadomienia (Android 13+)."""

from kivy.app import App
from kivy.core.window import Window

from pybrainroot.root import PyBrainRootView
from pybrainroot.ui import theme


class PyBrainRootApp(App):
    """Główna aplikacja PyBrainRoot."""

    def build(self) -> PyBrainRootView:
        Window.clearcolor = theme.BACKGROUND
        root = PyBrainRootView()
        # okno mogło powstać w ostatecznym rozmiarze, zanim App podpiął się
        # pod zdarzenie resize (np. natywny Wayland z HiDPI) — wtedy root
        # zostałby na domyślnych 100x100; ustawiamy rozmiar wprost
        root.size = Window.size
        self._request_notification_permission()
        return root

    @staticmethod
    def _request_notification_permission() -> None:
        """Prosi o zgodę na powiadomienia — potrzebną dla usługi tła."""
        try:
            from android.permissions import request_permissions

            request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except Exception:
            pass


def main() -> None:
    PyBrainRootApp().run()
