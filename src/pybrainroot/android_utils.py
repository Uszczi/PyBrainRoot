"""Pomocnicze funkcje Androida współdzielone przez aktywność i usługę tła.

Kod zależny od jnius jest wewnątrz funkcji — moduł importują zarówno
aktywność, jak i usługa p4a (osobny proces).
"""
import json
import os
import time

# jak często usługa tła sprawdza aplikację na pierwszym planie
MONITOR_INTERVAL_S = 2.0

# usługa dostępności (klasa Javy w android_src, deklarowana w manifeście
# przez hook p4a_hook.py) — zdarzeniowe źródło wykrywania aplikacji
ACCESSIBILITY_SERVICE_CLS = "org.pybrainroot.AppOpenAccessibilityService"

_CONFIG_NAME = "monitor_config.json"


# --------------------------------------------------------------------------
# Kontekst (aktywność albo usługa)
# --------------------------------------------------------------------------


def context():
    """Kontekst Androida — działa w procesie aktywności i w procesie usługi.

    Usługa p4a działa w osobnym procesie, w którym PythonActivity.mActivity
    nie istnieje — tam kontekstem jest instancja usługi (PythonService.mService).
    """
    from jnius import autoclass

    try:
        PythonService = autoclass("org.kivy.android.PythonService")
        if PythonService.mService:
            return PythonService.mService
    except Exception:
        pass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    return PythonActivity.mActivity


# --------------------------------------------------------------------------
# Wykrywanie aplikacji na pierwszym planie
# --------------------------------------------------------------------------


def foreground_package(ctx=None) -> str:
    """Zwraca nazwę pakietu aplikacji na pierwszym planie.

    Korzysta z UsageStatsManager — wymaga uprawnienia „Usage access”
    (Ustawienia → Aplikacje → Dostęp specjalny → Dostęp do użycia).
    Zdarzenia queryEvents aktualizują się na bieżąco, w przeciwieństwie
    do statystyk queryUsageStats, które potrafią się spóźniać.
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    UsageStatsManager = autoclass("android.app.usage.UsageStatsManager")
    # klasa wewnętrzna — pyjnius wymaga notacji z `$`
    UsageEvent = autoclass("android.app.usage.UsageEvents$Event")

    ctx = ctx or context()
    usm = ctx.getSystemService(Context.USAGE_STATS_SERVICE)
    now = int(time.time() * 1000)
    window_ms = 2 * 60 * 1000  # patrzymy na ostatnie 2 minuty

    try:
        events = usm.queryEvents(now - window_ms, now)
        ev = UsageEvent()
        pkg = ""
        while events.hasNextEvent():
            events.getNextEvent(ev)
            # ACTIVITY_RESUMED == MOVE_TO_FOREGROUND — aplikacja weszła
            # na pierwszy plan
            if ev.getEventType() == UsageEvent.ACTIVITY_RESUMED:
                pkg = ev.getPackageName()
        if pkg:
            return pkg
    except Exception:
        pass  # np. brak uprawnienia (SecurityException) — fallback niżej

    # fallback: statystyki użycia (mogą być opóźnione o kilka sekund)
    try:
        stats = usm.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY, now - window_ms, now
        )
        best_pkg, best_time = "", 0
        for entry in stats:
            if entry.getLastTimeUsed() > best_time:
                best_time = entry.getLastTimeUsed()
                best_pkg = entry.getPackageName()
        return best_pkg
    except Exception:
        return ""


def app_is_running(target: str, ctx=None) -> bool:
    """True, gdy aplikacja docelowa jest właśnie na pierwszym planie."""
    pkg = foreground_package(ctx).lower()
    return matches_target(pkg, target)


def matches_target(pkg: str, target: str) -> bool:
    """Czy pakiet `pkg` pasuje do celu `target` (porównanie podłańcuchowe).

    Cel może być fragmentem nazwy pakietu (np. „maps”); sprawdzamy dopasowanie
    w obie strony. `pkg` powinien być już sprowadzony do małych liter.
    """
    target = (target or "").strip().lower()
    return bool(pkg) and bool(target) and (target in pkg or pkg in target)


# --------------------------------------------------------------------------
# Uprawnienia
# --------------------------------------------------------------------------


def has_usage_access(ctx=None) -> bool:
    """True, gdy użytkownik przyznał PyBrainRoot „dostęp do użycia”."""
    from jnius import autoclass

    try:
        Context = autoclass("android.content.Context")
        AppOpsManager = autoclass("android.app.AppOpsManager")
        Process = autoclass("android.os.Process")
        ctx = ctx or context()
        appops = ctx.getSystemService(Context.APP_OPS_SERVICE)
        mode = appops.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            ctx.getPackageName(),
        )
        return mode == AppOpsManager.MODE_ALLOWED
    except Exception:
        return False


def can_draw_overlays(ctx=None) -> bool:
    """True, gdy aplikacja może rysować nad innymi aplikacjami."""
    from jnius import autoclass

    try:
        Settings = autoclass("android.provider.Settings")
        return Settings.canDrawOverlays(ctx or context())
    except Exception:
        return False


def has_accessibility_enabled(ctx=None) -> bool:
    """True, gdy użytkownik włączył usługę dostępności PyBrainRoot.

    Usługa dostępności to zdarzeniowe źródło wykrywania uruchamiania
    aplikacji — działa natychmiast i bez pollingu. Sprawdzamy ją przez
    ustawienie enabled_accessibility_services (lista spłaszczonych
    nazw komponentów rozdzielona dwukropkami).
    """
    from jnius import autoclass

    try:
        Settings = autoclass("android.provider.Settings")
        ctx = ctx or context()
        enabled = Settings.Secure.getString(
            ctx.getContentResolver(),
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        )
        component = f"{ctx.getPackageName()}/{ACCESSIBILITY_SERVICE_CLS}"
        return bool(enabled) and component in str(enabled)
    except Exception:
        return False


def open_accessibility_settings(ctx=None) -> None:
    """Otwiera ustawienia dostępności Androida (lista usług)."""
    from jnius import autoclass

    Settings = autoclass("android.provider.Settings")
    _start_settings_activity(
        ctx or context(), Settings.ACTION_ACCESSIBILITY_SETTINGS
    )


def _start_settings_activity(ctx, action: str, with_package_data: bool = False) -> None:
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    intent = Intent(action)
    if with_package_data:
        intent.setData(Uri.parse(f"package:{ctx.getPackageName()}"))
    # usługa nie jest aktywnością — bez NEW_TASK startActivity nie zadziała
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    ctx.startActivity(intent)


def open_usage_access_settings(ctx=None) -> None:
    """Otwiera ustawienia Androida: „Dostęp do użycia”."""
    from jnius import autoclass

    Settings = autoclass("android.provider.Settings")
    _start_settings_activity(ctx or context(), Settings.ACTION_USAGE_ACCESS_SETTINGS)


def open_overlay_settings(ctx=None) -> None:
    """Otwiera ustawienia: „Wyświetlanie na wierzchu innych aplikacji”."""
    from jnius import autoclass

    Settings = autoclass("android.provider.Settings")
    _start_settings_activity(
        ctx or context(),
        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
        with_package_data=True,
    )


# --------------------------------------------------------------------------
# Zamykanie aplikacji
# --------------------------------------------------------------------------


def close_app(target: str, ctx=None) -> bool:
    """Zamyka aplikację `target` (pełna nazwa pakietu Androida).

    killBackgroundProcesses działa tylko na procesach w tle, więc najpierw
    wracamy na ekran główny (HOME). Wymaga normalnego uprawnienia
    KILL_BACKGROUND_PROCESSES. Best effort — zwraca False, gdy się nie uda.
    """
    from jnius import autoclass

    target = (target or "").strip()
    if not target:
        return False
    try:
        Context = autoclass("android.content.Context")
        Intent = autoclass("android.content.Intent")
        ctx = ctx or context()
        if target == ctx.getPackageName():
            return False  # nigdy nie zamykaj samego PyBrainRoot
        # wróć na ekran główny — dzięki temu aplikacja trafia do tła
        home = Intent(Intent.ACTION_MAIN)
        home.addCategory(Intent.CATEGORY_HOME)
        home.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(home)
        am = ctx.getSystemService(Context.ACTIVITY_SERVICE)
        am.killBackgroundProcesses(target)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Konfiguracja monitorowania (plik współdzielony z usługą tła)
# --------------------------------------------------------------------------


def _config_path(ctx) -> str:
    # Uwaga: str(java.io.File) zwraca repr obiektu, a nie ścieżkę —
    # trzeba jawnie pobrać getAbsolutePath() (String jest już konwertowany
    # przez pyjnius na Pythona).
    return os.path.join(ctx.getFilesDir().getAbsolutePath(), _CONFIG_NAME)


def read_config(ctx=None) -> dict:
    """Czyta konfigurację monitorowania: {enabled, targets}."""
    ctx = ctx or context()
    try:
        with open(_config_path(ctx), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def targets_from_config(cfg: dict) -> list[str]:
    """Lista monitorowanych aplikacji z konfiguracji.

    Obsługuje też stary format z pojedynczym polem `target`.
    """
    targets = cfg.get("targets")
    if isinstance(targets, list):
        return [str(t).strip() for t in targets if str(t).strip()]
    legacy = str(cfg.get("target", "")).strip()
    return [legacy] if legacy else []


def write_config(ctx=None, **updates) -> None:
    """Aktualizuje konfigurację monitorowania (zapis atomowy)."""
    ctx = ctx or context()
    cfg = read_config(ctx)
    cfg.update(updates)
    path = _config_path(ctx)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Usługa tła (foreground service)
# --------------------------------------------------------------------------


def _service_class(ctx):
    from jnius import autoclass

    # p4a generuje klasę Service<Name> w pakiecie aplikacji (buildozer.spec
    # → `services`). Nazwę pakietu bierzemy z kontekstu, żeby nie zgadywać.
    return autoclass(f"{ctx.getPackageName()}.ServiceMonitor")


def start_monitor_service(ctx=None) -> None:
    """Uruchamia usługę monitorującą (z powiadomieniem stałym)."""
    ctx = ctx or context()
    _service_class(ctx).start(
        ctx,
        "",  # smallIconName — domyślna ikona aplikacji
        "PyBrainRoot",  # contentTitle powiadomienia stałego
        "Monitorowanie uruchamiania aplikacji",  # contentText
        "",  # pythonServiceArgument — konfigurację czytamy z pliku
    )


def stop_monitor_service(ctx=None) -> None:
    ctx = ctx or context()
    try:
        _service_class(ctx).stop(ctx)
    except Exception:
        pass  # usługa mogła już się zatrzymać — to nie błąd


def is_monitor_service_running(ctx=None) -> bool:
    """True, gdy usługa monitorująca jest uruchomiona.

    Na API 26+ getRunningServices zwraca tylko usługi tej aplikacji —
    dokładnie to, czego potrzebujemy.
    """
    from jnius import autoclass

    try:
        Context = autoclass("android.content.Context")
        ctx = ctx or context()
        am = ctx.getSystemService(Context.ACTIVITY_SERVICE)
        services = am.getRunningServices(100)
        pkg = ctx.getPackageName()
        for svc in services:
            name = str(svc.service.getClassName())
            if svc.service.getPackageName() == pkg and name.endswith(
                "ServiceMonitor"
            ):
                return True
        return False
    except Exception:
        return False
