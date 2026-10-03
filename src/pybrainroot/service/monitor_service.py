"""Usługa tła: monitoruje uruchamianie aplikacji, gdy PyBrainRoot jest w tle.

Wykrywanie zdarzeniowe: usługa dostępności (AppOpenAccessibilityService.java)
dostaje TYPE_WINDOW_STATE_CHANGED w momencie otwarcia aplikacji i wysyła
jawny broadcast; odbiorca w tym procesie (:service_monitor) wkłada nazwę
pakietu do kolejki mostu AppOpenBridge, na której pętla Pythona blokuje się
przez EVENTS.poll(timeout) — bez pollingu, z natychmiastowym budzeniem.

Fallback: gdy dostępność nie jest włączona (albo klasa mostu niedostępna —
stary APK), usługa odpytuje UsageStatsManager co MONITOR_INTERVAL_S.

Uruchamiana przez python-for-android (buildozer.spec → `services`) w osobnym
procesie `:service_monitor`. Flaga `:foreground` daje powiadomienie stałe.

Konfigurację czyta z pliku monitor_config.json (getFilesDir) zapisywanego
przez aktywność. Gdy `enabled` jest False — usługa sama się zatrzymuje.
"""
import os
import sys
import time

# katalog src/ jest trzy poziomy wyżej niż ten plik (src/pybrainroot/service/)
# — dzięki temu importy pybrainroot.* działają niezależnie od sys.path p4a
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from pybrainroot.android_overlay import show_overlay_modal  # noqa: E402
from pybrainroot.android_utils import (  # noqa: E402
    MONITOR_INTERVAL_S,
    close_app,
    context,
    foreground_package,
    has_accessibility_enabled,
    has_usage_access,
    matches_target,
    read_config,
    targets_from_config,
)

# w trybie zdarzeniowym usługa budzi się co tyle tylko na konserwację
# (przeładowanie konfiguracji, sprawdzenie stanu dostępności)
MAINTENANCE_INTERVAL_MS = 30_000


def log(msg: str) -> None:
    """Log diagnostyczny — stdout usługi trafia do logcat (tag usługi)."""
    print(f"[PyBrainRootService] {msg}")


def _event_queue():
    """Kolejka zdarzeń z mostu Java→Python (None, gdy klasa niedostępna)."""
    from jnius import autoclass

    try:
        return autoclass("org.pybrainroot.AppOpenBridge").EVENTS
    except Exception:
        return None


def _poll_events(events, timeout_ms: int):
    """Blokuje do `timeout_ms` na zdarzeniu; zwraca pakiet (str) albo None."""
    from jnius import autoclass

    TimeUnit = autoclass("java.util.concurrent.TimeUnit")
    pkg = events.poll(timeout_ms, TimeUnit.MILLISECONDS)
    return str(pkg).lower() if pkg is not None else None


def _notify_app_opened(ctx, target: str, pkg: str) -> None:
    """Reakcja na wykrycie uruchomienia aplikacji `target` — pokazuje modal."""
    log(f"WYKRYTO uruchomienie aplikacji: {target}")
    message = f"🚀 Uruchomiono aplikację: {target}"
    if not show_overlay_modal(
        "PyBrainRoot",
        message,
        # pkg to dokładny pakiet na pierwszym planie —
        # killBackgroundProcesses wymaga pełnej nazwy
        on_close=(lambda: close_app(pkg, ctx)) if pkg else None,
    ):
        # brak uprawnienia „Wyświetlanie na wierzchu” — modal nie pokazany
        log("overlay niedostępny — modal nie pokazany")
    else:
        log("pokazano modal")


def main() -> None:
    ctx = context()
    cfg = read_config(ctx)
    log(f"start: enabled={cfg.get('enabled')} targets={cfg.get('targets')!r}")
    if not cfg.get("enabled"):
        log("monitorowanie wyłączone w konfiguracji — usługa kończy działanie")
        return  # nic do roboty — po wyjściu z main() usługa się zatrzyma

    targets = targets_from_config(cfg)
    was_running: dict[str, bool] = {}
    usage_warned = False
    events = _event_queue()
    log(f"monitoruję {len(targets)} aplikacji")

    while True:
        cfg = read_config(ctx)
        if not cfg.get("enabled"):
            log("enabled=false — usługa kończy działanie")
            break
        new_targets = targets_from_config(cfg)
        if set(new_targets) != set(targets):
            targets = new_targets
            was_running = {}
            log(f"zmiana listy celów: {targets!r}")

        if events is not None and has_accessibility_enabled(ctx):
            # tryb zdarzeniowy: blokujemy na kolejce mostu — budzenie tylko
            # przy realnym zdarzeniu; timeout to przerwa na konserwację
            pkg = _poll_events(events, MAINTENANCE_INTERVAL_MS)
            if pkg is None:
                continue
        else:
            # fallback: polling UsageStats (wymaga „Dostępu do użycia”)
            if not has_usage_access(ctx):
                if not usage_warned:
                    log("BRAK dostępu do użycia — monitoring nie wykryje aplikacji")
                    usage_warned = True
                time.sleep(MONITOR_INTERVAL_S)
                continue
            usage_warned = False
            time.sleep(MONITOR_INTERVAL_S)
            # jedna wspólna kwerenda o pakiet na pierwszym planie
            pkg = foreground_package(ctx).lower() if targets else ""
            if not pkg:
                continue

        for target in targets:
            running = matches_target(pkg, target)
            if running and not was_running.get(target, False):
                # wykryto „przejście” z wyłączonej na włączoną → pokaż modal
                _notify_app_opened(ctx, target, pkg)
            was_running[target] = running

    stop_service()


def stop_service() -> None:
    """Zatrzymuje usługę (wywołane na końcu main())."""
    from jnius import autoclass

    try:
        PythonService = autoclass("org.kivy.android.PythonService")
        if PythonService.mService:
            PythonService.mService.stopSelf()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        print("[PyBrainRootService] FATAL — wyjątek w main():")
        traceback.print_exc()
