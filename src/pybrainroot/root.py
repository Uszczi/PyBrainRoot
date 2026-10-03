"""Kontroler aplikacji: stan monitorowania i przełączanie ekranów.

PyBrainRootView (ScreenManager) trzyma cały stan aplikacji:
- wybrane aplikacje do monitorowania (SQLite — przeżywają restart),
- flagę monitorowania i poprzedni stan „aplikacja działa” (dla pollingu),
- ekrany: główny i listy aplikacji.
"""

from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager

from pybrainroot import android_overlay, android_utils, storage
from pybrainroot.ui import theme
from pybrainroot.ui.apps import AppsScreen
from pybrainroot.ui.main_screen import MainScreen
from pybrainroot.ui.modal import build_modal_content


def get_root() -> "PyBrainRootView":
    """Bieżący kontroler aplikacji (dostępny po wystartowaniu Kivy)."""
    from kivy.app import App

    return App.get_running_app().root


class PyBrainRootView(ScreenManager):
    """Korzeń aplikacji — trzyma stan monitorowania i przełącza ekrany."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.monitoring = False
        # wybrane aplikacje trzymamy w SQLite — przeżywają restart aplikacji
        self.monitored_targets: set[str] = storage.load_monitored_targets()
        # dla pollingu: poprzedni stan „aplikacja działa / nie działa”
        self.was_running: dict[str, bool] = {}
        self._popup: Popup | None = None
        self._monitor_event = None
        self.main_screen = MainScreen(self)
        self.apps_screen = AppsScreen(self)
        self.add_widget(self.main_screen)
        self.add_widget(self.apps_screen)
        self._restore_state()

    # ---------------------------------------------------- wybór aplikacji

    def toggle_target(self, target: str, monitored: bool, name: str = "") -> None:
        """Zaznacza/odznacza aplikację jako monitorowaną (z zapisem w SQLite)."""
        target = (target or "").strip()
        if not target:
            return
        if monitored:
            self.monitored_targets.add(target)
            storage.save_monitored_target(target, name)
        else:
            self.monitored_targets.discard(target)
            storage.delete_monitored_target(target)
        if self.monitoring:
            # usługa tła przeczyta zmiany przy najbliższym takcie
            self._sync_config()
        self.apps_screen.update_count()

    def _sync_config(self) -> None:
        """Zapisuje bieżące cele do pliku konfiguracji usługi tła."""
        try:
            android_utils.write_config(targets=sorted(self.monitored_targets))
        except Exception:
            pass

    # ---------------------------------------------------------------- modal

    def notify(self, message: str, target: str = "") -> None:
        """Pokazuje modal — nakładkę systemową nad aktualnie otwartą aplikacją.

        Działa też, gdy PyBrainRoot jest w tle. Gdy brakuje uprawnienia
        „Wyświetlanie na wierzchu”, wracamy do popupu Kivy.
        Gdy podano `target`, modal dostaje guzik „Zamknij aplikację”,
        który zamyka właśnie uruchomioną aplikację.
        """
        on_close = self._close_foreground_callback() if target else None
        if android_overlay.show_overlay_modal(
            "PyBrainRoot", message, on_close=on_close
        ):
            return
        self.show_modal(message, target=target or None)

    @staticmethod
    def _close_foreground_callback():
        """Funkcja zamykająca aplikację na pierwszym planie (albo None).

        Cele mogą być wzorcami (np. „maps”), a killBackgroundProcesses
        wymaga pełnej nazwy pakietu — bierzemy pakiet na pierwszym planie.
        """
        pkg = android_utils.foreground_package()
        return (lambda: android_utils.close_app(pkg)) if pkg else None

    def show_modal(self, message: str, target: str | None = None) -> None:
        """Okno modalne — blokuje resztę aplikacji do czasu zamknięcia.

        Gdy podano `target`, modal zawiera guzik „Zamknij aplikację”,
        który kończy działanie właśnie uruchomionej aplikacji.
        """
        on_close = (lambda: self._close_launched_app(target)) if target else None
        self._popup = Popup(
            title="PyBrainRoot",
            title_color=theme.TEXT,
            title_size="20sp",
            separator_color=theme.PRIMARY,
            content=build_modal_content(message, on_close=on_close),
            size_hint=(0.82, 0.45),
            auto_dismiss=True,
        )
        self._popup.open()

    def _close_launched_app(self, target: str) -> None:
        """Zamyka modal i kończy działanie właśnie uruchomionej aplikacji."""
        if self._popup:
            self._popup.dismiss()
        android_utils.close_app(target)

    def on_button_clicked(self) -> None:
        self.notify("Hej! Kliknięto guzik 👋")

    # ---------------------------------------------------------- monitoring

    def toggle_monitoring(self) -> None:
        if self.monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        targets = sorted(self.monitored_targets)
        if not targets:
            self.status_label.text = "Najpierw zaznacz aplikacje do monitorowania."
            self.current = "apps"
            return
        if not self._has_detection_source():
            self.status_label.text = (
                "Brak wykrywania! Włącz »Dostępność« albo »Dostęp do użycia«."
            )
            self.notify(
                "Brak uprawnień wykrywania — włącz dostępność "
                "(zalecane) albo dostęp do użycia."
            )
            return
        # Monitoruje usługa tła (foreground service) — działa również,
        # gdy PyBrainRoot nie jest otwarte.
        try:
            android_utils.write_config(targets=targets, enabled=True)
        except Exception:
            # problem z plikiem konfiguracyjnym — usługa i tak nie
            # miałaby czego monitorować, wracamy do trybu na pierwszym planie
            self._start_foreground_monitoring(targets)
            return
        try:
            android_utils.start_monitor_service()
        except Exception:
            # usługa niedostępna (np. stary APK bez usługi) — fallback
            self._start_foreground_monitoring(targets)
            return
        self.monitoring = True
        self.monitor_button.text = "⏹ Stop"
        self._update_status_after_start(targets)

    @staticmethod
    def _has_detection_source() -> bool:
        """Czy włączony jest którykolwiek mechanizm wykrywania aplikacji."""
        return (
            android_utils.has_usage_access()
            or android_utils.has_accessibility_enabled()
        )

    def _update_status_after_start(self, targets: list[str]) -> None:
        if not android_utils.can_draw_overlays():
            self.status_label.text = (
                "Monitoring w tle. Przyznaj »Wyświetlanie na wierzchu«, "
                "by modal pokazywał się nad innymi aplikacjami."
            )
            android_utils.open_overlay_settings()
        elif not android_utils.has_accessibility_enabled():
            self.status_label.text = (
                f"Monitorowanie w tle (polling): {len(targets)} aplikacji. "
                "Włącz »Dostępność« dla natychmiastowego wykrywania."
            )
        else:
            self.status_label.text = (
                f"Monitorowanie w tle: {len(targets)} aplikacji"
            )

    def _start_foreground_monitoring(self, targets: list[str]) -> None:
        """Monitorowanie bez usługi tła — działa, gdy aplikacja jest otwarta.

        Fallback, gdy usługa tła nie mogła wystartować.
        """
        self.monitoring = True
        self.was_running = {
            t: android_utils.app_is_running(t) for t in targets
        }
        self.monitor_button.text = "⏹ Stop"
        self.status_label.text = (
            f"Monitorowanie (tylko na pierwszym planie): {len(targets)} aplikacji"
        )
        self._monitor_event = Clock.schedule_interval(
            self._check_target, android_utils.MONITOR_INTERVAL_S
        )

    def _stop_monitoring(self) -> None:
        self.monitoring = False
        self.monitor_button.text = "▶ Start"
        self.status_label.text = "Monitorowanie: wyłączone"
        try:
            android_utils.write_config(enabled=False)
        except Exception:
            pass
        android_utils.stop_monitor_service()
        if self._monitor_event is not None:
            self._monitor_event.cancel()
            self._monitor_event = None

    def _restore_state(self) -> None:
        """Po ponownym otwarciu aplikacji wznawia monitoring, gdy był włączony.

        Jeśli usługa żyje (flaga `sticky` — przeżywa wysunięcie aplikacji
        z listy ostatnich) — tylko odtwarzamy stan widoku. Jeśli nie żyje
        (np. restart telefonu albo force-stop) — uruchamiamy ją ponownie,
        żeby monitoring działał dalej bez klikania „Start”.
        """
        cfg = android_utils.read_config()
        if not cfg.get("enabled"):
            return
        targets = android_utils.targets_from_config(cfg)
        if not targets:
            return
        if not android_utils.is_monitor_service_running():
            # usługa nie żyje — spróbuj wznowić (aplikacja jest na
            # pierwszym planie, więc start FGS jest dozwolony)
            try:
                android_utils.start_monitor_service()
            except Exception:
                try:
                    android_utils.write_config(enabled=False)
                except Exception:
                    pass
                return
        self.monitored_targets = set(targets)
        self.monitoring = True
        self.monitor_button.text = "⏹ Stop"
        self.status_label.text = f"Monitorowanie w tle: {len(targets)} aplikacji"

    def _check_target(self, _dt) -> None:
        for target in self.was_running:
            running = android_utils.app_is_running(target)
            if running and not self.was_running[target]:
                # wykryto „przejście” z wyłączonej na włączoną → powiadom
                self.notify(f"🚀 Uruchomiono aplikację: {target}", target=target)
                self.status_label.text = f"Monitorowanie: wykryto {target}"
            self.was_running[target] = running

    # ------------------------------------------- widżety żyjące na ekranach

    @property
    def monitor_button(self):
        """Guzik start/stop (należy do ekranu głównego)."""
        return self.main_screen.monitor_button

    @property
    def status_label(self):
        """Etykieta statusu (należy do ekranu głównego)."""
        return self.main_screen.status_label
