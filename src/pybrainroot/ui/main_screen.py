"""Ekran główny: guzik testowy, start/stop monitorowania, ustawienia."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from pybrainroot import android_utils
from pybrainroot.ui import theme


class MainScreen(Screen):
    """Główny ekran: guzik, przełącznik modala, start/stop monitorowania.

    Guziki `monitor_button` i `status_label` są atrybutami tego ekranu,
    ale zmienia je kontroler (PyBrainRootView) — stąd publiczne nazwy.
    """

    def __init__(self, root, **kwargs) -> None:
        super().__init__(name="main", **kwargs)
        self.root = root
        self.monitor_button = None
        self.status_label = None
        self.layout = BoxLayout(orientation="vertical", padding=24, spacing=10)
        self.add_widget(self.layout)
        self._build_ui()

    def _build_ui(self) -> None:
        self.layout.add_widget(
            theme.label(
                "PyBrainRoot",
                bold=True,
                font_size="28sp",
                size_hint_y=None,
                height=52,
            )
        )
        self.layout.add_widget(
            theme.label(
                "Guzik, modal i monitoring aplikacji",
                color=theme.SUBTLE,
                font_size="15sp",
                size_hint_y=None,
                height=30,
            )
        )

        self.layout.add_widget(
            theme.button("🔔 Pokaż modal", self.root.on_button_clicked)
        )
        self.layout.add_widget(
            theme.button("📋 Zarządzaj aplikacjami", self._open_apps)
        )

        # start / stop
        self.monitor_button = theme.button("▶ Start", self.root.toggle_monitoring)
        self.layout.add_widget(self.monitor_button)

        # zdarzeniowe wykrywanie przez usługę dostępności — zalecane
        # (natychmiastowe, bez pollingu); „Dostęp do użycia” to fallback
        self.layout.add_widget(
            theme.button(
                "Dostępność (szybkie wykrywanie)",
                android_utils.open_accessibility_settings,
                height=56,
                color=theme.SURFACE,
                text_color=theme.TEXT,
            )
        )
        self.layout.add_widget(
            theme.button(
                "Dostęp do użycia",
                android_utils.open_usage_access_settings,
                height=56,
                color=theme.SURFACE,
                text_color=theme.TEXT,
            )
        )
        # „Wyświetlanie na wierzchu” — bez tego modal nie pokaże się
        # nad innymi aplikacjami
        self.layout.add_widget(
            theme.button(
                "Wyświetlanie na wierzchu",
                android_utils.open_overlay_settings,
                height=56,
                color=theme.SURFACE,
                text_color=theme.TEXT,
            )
        )

        self.status_label = theme.label(
            "Monitorowanie: wyłączone",
            color=theme.SUBTLE,
            valign="top",
            size_hint_y=None,
            height=30,
        )
        self.layout.add_widget(self.status_label)

    def _open_apps(self) -> None:
        self.root.current = "apps"
