"""Symulacja części androidowych — do uruchamiania UI na desktopie (Linux).

Bez tego modułu aplikacja na desktopie pada na `import jnius` przy pierwszej
funkcji zależnej od Androida. `apply_mocks()` podmienia te funkcje na
odpowiedniki działające bez urządzenia:

- baza SQLite i monitor_config.json lądują w ~/.pybrainroot-desktop,
- „usługa tła” nie istnieje — start_monitor_service rzuca wyjątek, przez co
  kontroler sam przechodzi na monitorowanie na pierwszym planie (Kivy Clock),
- nakładka systemowa jest niedostępna — modal pokazuje się jako popup Kivy,
- lista zainstalowanych aplikacji to FAKE_APPS, a `launch_app()`/`go_home()`
  symulują wchodzenie aplikacji na pierwszy plan.
"""
import json
import threading
import time
from pathlib import Path

from pybrainroot import android_utils, storage
from pybrainroot.ui import apps as apps_ui

# stan desktopowy trzymamy poza projektem — w katalogu użytkownika
STATE_DIR = Path.home() / ".pybrainroot-desktop"

# symulowana lista zainstalowanych aplikacji: (nazwa wyświetlana, pakiet)
FAKE_APPS: list[tuple[str, str]] = [
    ("Mapy Google", "com.google.maps"),
    ("YouTube", "com.google.android.youtube"),
    ("Instagram", "com.instagram.android"),
    ("Chrome", "com.android.chrome"),
    ("Zegar", "com.google.android.deskclock"),
    ("Ustawienia", "com.android.settings"),
]

LAUNCHER = "com.android.launcher"

_foreground = LAUNCHER
_lock = threading.Lock()
_demo_thread: threading.Thread | None = None
_demo_stop = threading.Event()


# ---------------------------------------------------------------- symulacja

def current_foreground() -> str:
    """Pakiet „widoczny na pierwszym planie” (symulowany)."""
    with _lock:
        return _foreground


def launch_app(pkg: str) -> None:
    """Symuluje wejście aplikacji `pkg` na pierwszy plan."""
    global _foreground
    with _lock:
        _foreground = pkg or LAUNCHER
    print(f"[desktop] otwarto aplikację: {_foreground}")


def go_home() -> None:
    """Symuluje powrót na ekran główny (launcher)."""
    launch_app(LAUNCHER)


def _close_app(target: str, *args, **kwargs) -> bool:
    """Symuluje zamknięcie aplikacji — wraca na launcher."""
    print(f"[desktop] zamknięto aplikację: {target}")
    go_home()
    return True


def _app_is_running(target: str, *args, **kwargs) -> bool:
    return android_utils.matches_target(current_foreground(), target)


def _start_service(*args, **kwargs) -> None:
    """Na desktopie nie ma usługi tła — rzucamy, by kontroler przeszedł
    na monitorowanie na pierwszym planie (Kivy Clock)."""
    raise RuntimeError("[desktop] brak usługi tła — fallback na pierwszy plan")


def _noop_settings(name: str):
    """Pseudo-otwieranie ustawień Androida (na desktopie pomijane)."""

    def open_settings(*args, **kwargs) -> None:
        print(f"[desktop] ustawienia „{name}” — na desktopie pomijam")

    return open_settings


# ------------------------------------------------------- stan (pliki lokalne)

def _config_path() -> Path:
    return STATE_DIR / "monitor_config.json"


def _read_config() -> dict:
    try:
        return json.loads(_config_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(**updates) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _read_config()
    cfg.update(updates)
    tmp = _config_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_config_path())


def _db_path() -> str:
    """Baza SQLite działa na desktopie natywnie — tylko inny katalog."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return str(STATE_DIR / "pybrainroot.db")


# ------------------------------------------------------------- instalowanie

def apply_mocks() -> None:
    """Podmienia funkcje zależne od Androida na symulowane odpowiedniki."""
    android_utils.context = lambda *a, **k: None
    android_utils.has_usage_access = lambda *a, **k: True
    android_utils.has_accessibility_enabled = lambda *a, **k: False
    # bez nakładki systemowej — modal pokaże się jako popup Kivy
    android_utils.can_draw_overlays = lambda *a, **k: False
    android_utils.foreground_package = lambda *a, **k: current_foreground()
    android_utils.app_is_running = _app_is_running
    android_utils.close_app = _close_app
    android_utils.read_config = lambda *a, **k: _read_config()
    android_utils.write_config = lambda *a, **updates: _write_config(**updates)
    android_utils.start_monitor_service = _start_service
    android_utils.stop_monitor_service = lambda *a, **k: None
    android_utils.is_monitor_service_running = lambda *a, **k: False
    android_utils.open_accessibility_settings = _noop_settings("Dostępność")
    android_utils.open_usage_access_settings = _noop_settings("Dostęp do użycia")
    android_utils.open_overlay_settings = _noop_settings(
        "Wyświetlanie na wierzchu"
    )

    storage._db_path = _db_path

    apps_ui.list_installed_apps = lambda: sorted(
        FAKE_APPS, key=lambda pair: pair[0].lower()
    )


# ------------------------------------------------------- automatyczna demonstracja

def start_auto_demo(interval_s: float = 8.0) -> None:
    """W tle „otwiera” kolejno monitorowane aplikacje, by zobaczyć modale.

    Działa tylko wtedy, gdy coś jest monitorowane (czyta zapisany zbiór
    celów). Przed każdą zmianą zamyka otwarty popup (na wątku Kivy).
    """
    global _demo_thread
    if _demo_thread is not None:
        return
    _demo_stop.clear()

    def close_open_popup() -> None:
        try:
            from kivy.app import App
            from kivy.clock import Clock
        except Exception:
            return
        app = App.get_running_app()
        if app is None:
            return
        popup = getattr(getattr(app, "root", None), "_popup", None)
        if popup is not None:
            Clock.schedule_once(lambda _dt: popup.dismiss(), 0)

    counter = 0

    def loop() -> None:
        nonlocal counter
        while not _demo_stop.is_set():
            time.sleep(interval_s)
            try:
                targets = sorted(storage.load_monitored_targets())
            except Exception:
                targets = []
            if not targets:
                continue
            close_open_popup()
            if len(targets) == 1 and counter % 2 == 1:
                go_home()  # przy jednym celu: otwórz → wróć → otwórz…
            else:
                launch_app(targets[counter % len(targets)])
            counter += 1

    _demo_thread = threading.Thread(target=loop, daemon=True)
    _demo_thread.start()


def stop_auto_demo() -> None:
    """Zatrzymuje automatyczną demonstrację."""
    global _demo_thread
    _demo_stop.set()
    if _demo_thread is not None:
        _demo_thread.join(timeout=2.0)
        _demo_thread = None
