"""Ekran „Aplikacje”: lista zainstalowanych aplikacji z wyszukiwarką."""

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen

from pybrainroot.ui import theme

ROW_HEIGHT = 60  # wysokość wiersza listy (dp)


# --------------------------------------------------------------------------
# Lista zainstalowanych aplikacji (Android)
# --------------------------------------------------------------------------


def list_installed_apps() -> list[tuple[str, str]]:
    """Zwraca listę zainstalowanych aplikacji jako pary
    (nazwa wyświetlana, nazwa pakietu) — przez PackageManager.
    """
    from jnius import autoclass  # dostępne tylko w kompilacji dla Androida

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    pm = PythonActivity.mActivity.getPackageManager()
    # toArray() zwraca zwykłą listę Pythona — łatwiej po niej iterować
    infos = pm.getInstalledApplications(0).toArray()

    apps: list[tuple[str, str]] = []
    for info in infos:
        try:
            label = str(info.loadLabel(pm))
            package = str(info.packageName)
            if label and package:
                apps.append((label, package))
        except Exception:
            continue
    apps.sort(key=lambda pair: pair[0].lower())
    return apps


class AppsRow(RecycleDataViewBehavior, BoxLayout):
    """Wiersz listy: checkbox + nazwa aplikacji. Zaznaczenie = monitorowana."""

    index: int | None = None
    data: dict | None = None

    def __init__(self, **kwargs) -> None:
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(ROW_HEIGHT),
            **kwargs,
        )
        self._updating = False
        self.checkbox = theme.checkbox(size_hint_x=None, width=48)
        self.checkbox.bind(active=self._on_toggle)
        self.add_widget(self.checkbox)
        self.label = theme.label(
            "", markup=True, padding=(4, 0), font_size="16sp"
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)

    def refresh_view_attrs(self, rv, index, data) -> None:
        self.index = index
        self.data = data
        self._updating = True
        try:
            self.checkbox.active = bool(data.get("active", False))
        finally:
            self._updating = False
        self.label.text = (
            f"[b]{data.get('name', '')}[/b]\n"
            f"[size=12sp][color={theme.SUBTLE_HEX}]"
            f"{data.get('target', '')}[/color][/size]"
        )
        return super().refresh_view_attrs(rv, index, data)

    def _on_toggle(self, _checkbox, value) -> None:
        if self._updating or self.data is None:
            return
        # import opóźniony — unikamy cyklu importów (root → ui.apps)
        from pybrainroot.root import get_root

        self.data["active"] = bool(value)
        get_root().toggle_target(
            self.data.get("target", ""),
            bool(value),
            self.data.get("name", ""),
        )


class AppsScreen(Screen):
    """Ekran zarządzania: lista zainstalowanych aplikacji + wyszukiwarka."""

    def __init__(self, root, **kwargs) -> None:
        super().__init__(name="apps", **kwargs)
        self.root = root
        self.all_apps: list[tuple[str, str]] = []
        self._loaded = False
        self.layout = BoxLayout(orientation="vertical", padding=16, spacing=10)
        self.add_widget(self.layout)
        self._build_ui()
        self.bind(on_enter=lambda *_args: self._refresh())

    # ------------------------------------------------------------ budowa UI

    def _build_ui(self) -> None:
        self.layout.add_widget(self._build_top_bar())

        self.filter_input = theme.text_input("Szukaj po nazwie lub pakiecie…")
        self.filter_input.bind(text=lambda *_args: self._apply_filter())
        self.layout.add_widget(self.filter_input)

        self.rv = self._build_list()
        self.layout.add_widget(self.rv)

        self.count_label = theme.label(
            "Monitorowane: 0",
            color=theme.SUBTLE,
            size_hint_y=None,
            height=30,
        )
        self.layout.add_widget(self.count_label)

    def _build_top_bar(self) -> BoxLayout:
        top = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=dp(56)
        )
        back = theme.button(
            "← Wróć",
            self._go_back,
            height=44,
            width=120,
            size_hint_x=None,
            color=theme.SURFACE,
        )
        top.add_widget(back)
        top.add_widget(
            theme.label(
                "Aplikacje do monitorowania",
                bold=True,
                font_size="18sp",
            )
        )
        return top

    def _build_list(self) -> RecycleView:
        rv = RecycleView()
        layout_manager = RecycleBoxLayout(
            orientation="vertical",
            default_size=(None, dp(ROW_HEIGHT)),  # wysokość wiersza z danych
            default_size_hint=(1, None),
            size_hint_y=None,
        )
        layout_manager.bind(minimum_height=layout_manager.setter("height"))
        # kolejność ma znaczenie: najpierw layout manager, potem viewclass
        rv.add_widget(layout_manager)
        rv.viewclass = AppsRow
        return rv

    # -------------------------------------------------------- dane / filtry

    def _go_back(self) -> None:
        self.root.current = "main"

    def _refresh(self) -> None:
        """(Prze)ładowanie listy przy wejściu na ekran."""
        if not self._loaded:
            self.all_apps = list_installed_apps()
            self._loaded = True
        self._apply_filter()
        self.update_count()

    def _apply_filter(self) -> None:
        query = self.filter_input.text.strip().lower()
        rows = [
            self._row(name, target)
            for name, target in self.all_apps
            if self._matches(name, target, query)
        ]
        self.rv.data = rows or [self._empty_row()]

    @staticmethod
    def _matches(name: str, target: str, query: str) -> bool:
        return not query or query in name.lower() or query in target.lower()

    def _row(self, name: str, target: str) -> dict:
        return {
            "name": name,
            "target": target,
            "active": target in self.root.monitored_targets,
        }

    @staticmethod
    def _empty_row() -> dict:
        return {
            "name": "Brak aplikacji pasujących do filtra.",
            "target": "",
            "active": False,
        }

    def update_count(self) -> None:
        """Odświeża licznik monitorowanych aplikacji (wywołuje kontroler)."""
        self.count_label.text = f"Monitorowane: {len(self.root.monitored_targets)}"
