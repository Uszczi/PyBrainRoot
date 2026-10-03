"""Modal-nakładka rysowana NAD innymi aplikacjami (Android).

Wymaga uprawnienia SYSTEM_ALERT_WINDOW („Wyświetlanie na wierzchu innych
aplikacji”). W przeciwieństwie do kivy.uix.popup.Popup okno WindowManager
jest widoczne również wtedy, gdy PyBrainRoot nie jest na pierwszym planie —
np. nad aplikacją, której uruchomienie właśnie wykryto.

Usługa p4a wykonuje kod Pythona na wątku bez pętli zdarzeń, więc budowanie
i usuwanie widoków marszrutujemy na główny wątek procesu przez Handler.
"""
import threading

from pybrainroot.android_utils import can_draw_overlays, context

# kolory nakładki
_CARD_COLOR = "#2E3340"
_TITLE_COLOR = "#FFFFFF"
_TEXT_COLOR = "#DCE3EE"
_ACCENT_COLOR = "#3D6FB4"
_DANGER_COLOR = "#A84444"

_OVERLAY = None  # aktywna nakładka — referencja, żeby GC nie zwolnił widoków
_RUNNERS = []  # Runnable czekające na wykonanie na głównym wątku


class _OverlayState:
    """Stan aktywnej nakładki: widoki, słuchacze, funkcje sprzątające."""

    def __init__(self, root, listener, close_listener, on_close, dismiss, wm):
        self.root = root
        self.listener = listener
        self.close_listener = close_listener
        self.on_close = on_close
        self.dismiss = dismiss
        self.wm = wm
        self.timer: threading.Timer | None = None
        self.removed = False


def _post_to_main(fn) -> None:
    """Wykonuje `fn` na głównym wątku procesu."""
    from jnius import PythonJavaClass, autoclass, java_method

    Handler = autoclass("android.os.Handler")
    Looper = autoclass("android.os.Looper")

    class Runnable(PythonJavaClass):
        __javainterfaces__ = ["java/lang/Runnable"]

        def __init__(self, fn):
            super().__init__()
            self.fn = fn

        @java_method("()V")
        def run(self):
            try:
                _RUNNERS.remove(self)
            except ValueError:
                pass
            self.fn()

    runnable = Runnable(fn)
    _RUNNERS.append(runnable)
    Handler(Looper.getMainLooper()).post(runnable)


def _on_main_thread() -> bool:
    """True, gdy działamy na głównym wątku procesu (np. wątek Kivy)."""
    from jnius import autoclass

    Looper = autoclass("android.os.Looper")
    return Looper.myLooper() == Looper.getMainLooper()


def _build_views(ctx, title: str, message: str, timeout_s: float, on_close=None) -> None:
    """Buduje widoki nakładki i dodaje je do WindowManager (główny wątek)."""
    global _OVERLAY
    from jnius import PythonJavaClass, autoclass, java_method

    LinearLayout = autoclass("android.widget.LinearLayout")
    TextView = autoclass("android.widget.TextView")
    Button = autoclass("android.widget.Button")
    Gravity = autoclass("android.view.Gravity")
    Color = autoclass("android.graphics.Color")
    GradientDrawable = autoclass("android.graphics.drawable.GradientDrawable")
    Typeface = autoclass("android.graphics.Typeface")
    Context = autoclass("android.content.Context")
    BuildVersion = autoclass("android.os.Build$VERSION")
    # klasy wewnętrzne wymagają w pyjnius notacji z `$` — atrybut
    # `LinearLayout.LayoutParams` nie jest rozpoznawany
    LinearLayoutParams = autoclass("android.widget.LinearLayout$LayoutParams")
    ViewGroupParams = autoclass("android.view.ViewGroup$LayoutParams")
    WindowManagerParams = autoclass("android.view.WindowManager$LayoutParams")

    density = ctx.getResources().getDisplayMetrics().density

    def dp(value: float) -> int:
        return int(value * density)

    # pyjnius NIE konwertuje automatycznie Pythona str na CharSequence
    # (parametry setText / setContentTitle itp.) — trzeba jawnie utworzyć
    # java.lang.String. Dla dokładnego typu String konwersja działa sama.
    JavaString = autoclass("java.lang.String")

    wm = ctx.getSystemService(Context.WINDOW_SERVICE)

    class ClickListener(PythonJavaClass):
        __javainterfaces__ = ["android/view/View$OnClickListener"]

        def __init__(self, fn):
            super().__init__()
            self.fn = fn

        @java_method("(Landroid/view/View;)V")
        def onClick(self, view):
            self.fn()

    def dismiss() -> None:
        global _OVERLAY
        if _OVERLAY is None or _OVERLAY.removed:
            return
        _OVERLAY.removed = True
        if _OVERLAY.timer:
            _OVERLAY.timer.cancel()
        try:
            wm.removeView(_OVERLAY.root)
        except Exception:
            pass  # system mógł już usunąć okno (np. śmierć procesu)
        _OVERLAY = None

    def make_button(text: str, color_hex: str, top_margin: int):
        """Guzik na całą szerokość z zaokrąglonym tłem w kolorze `color_hex`."""
        btn = Button(ctx)
        btn.setText(JavaString(text))
        btn.setTextColor(Color.parseColor(_TITLE_COLOR))
        btn.setTextSize(15)
        background = GradientDrawable()
        background.setColor(Color.parseColor(color_hex))
        background.setCornerRadius(dp(10))
        btn.setBackground(background)
        params = LinearLayoutParams(
            ViewGroupParams.MATCH_PARENT, ViewGroupParams.WRAP_CONTENT
        )
        params.setMargins(0, dp(top_margin), 0, 0)
        btn.setLayoutParams(params)
        return btn

    root = LinearLayout(ctx)
    root.setOrientation(LinearLayout.VERTICAL)
    root.setPadding(dp(22), dp(20), dp(22), dp(18))
    root.setElevation(dp(12))

    card = GradientDrawable()
    card.setColor(Color.parseColor(_CARD_COLOR))
    card.setCornerRadius(dp(16))
    root.setBackground(card)

    title_tv = TextView(ctx)
    title_tv.setText(JavaString(title))
    title_tv.setTextColor(Color.parseColor(_TITLE_COLOR))
    title_tv.setTextSize(18)
    title_tv.setTypeface(Typeface.DEFAULT_BOLD)
    title_tv.setGravity(Gravity.CENTER)
    root.addView(title_tv)

    msg_tv = TextView(ctx)
    msg_tv.setText(JavaString(message))
    msg_tv.setTextColor(Color.parseColor(_TEXT_COLOR))
    msg_tv.setTextSize(15)
    msg_tv.setGravity(Gravity.CENTER)
    msg_tv.setPadding(0, dp(10), 0, dp(6))
    root.addView(msg_tv)

    listener = ClickListener(dismiss)
    root.setOnClickListener(listener)  # dotknięcie gdziekolwiek zamyka modal

    ok = make_button("OK", _ACCENT_COLOR, top_margin=10)
    ok.setOnClickListener(listener)
    root.addView(ok)

    close = None
    close_listener = None
    if on_close:

        def close_and_dismiss():
            try:
                on_close()
            except Exception:
                print("[overlay] błąd przy zamykaniu aplikacji:")
                import traceback

                traceback.print_exc()
            dismiss()

        close_listener = ClickListener(lambda: close_and_dismiss())
        close = make_button("✖ Zamknij aplikację", _DANGER_COLOR, top_margin=8)
        close.setOnClickListener(close_listener)
        root.addView(close)

    metrics = ctx.getResources().getDisplayMetrics()

    lp = WindowManagerParams()
    if BuildVersion.SDK_INT >= 26:
        lp.type = WindowManagerParams.TYPE_APPLICATION_OVERLAY
    else:
        # Android 7.x: starszy typ okna, to samo uprawnienie SYSTEM_ALERT_WINDOW
        lp.type = WindowManagerParams.TYPE_PHONE
    lp.format = 1  # PixelFormat.TRANSLUCENT
    # bez fokusu i bez przechwytywania dotknięć poza nakładką — aplikacja
    # pod spodem pozostaje interaktywna
    lp.flags = (
        WindowManagerParams.FLAG_NOT_FOCUSABLE
        | WindowManagerParams.FLAG_NOT_TOUCH_MODAL
    )
    lp.gravity = Gravity.CENTER
    lp.width = int(metrics.widthPixels * 0.86)
    lp.height = ViewGroupParams.WRAP_CONTENT

    _OVERLAY = _OverlayState(
        root=root,
        listener=listener,
        close_listener=close_listener,
        on_close=on_close,
        dismiss=dismiss,
        wm=wm,
    )
    wm.addView(root, lp)

    if timeout_s:
        # Timer działa na własnym wątku — usunięcie widoku przekazujemy
        # na główny wątek
        _OVERLAY.timer = threading.Timer(timeout_s, lambda: _post_to_main(dismiss))
        _OVERLAY.timer.daemon = True
        _OVERLAY.timer.start()


def show_overlay_modal(
    title: str, message: str, timeout_s: float = 12.0, on_close=None
) -> bool:
    """Pokazuje modal nad wszystkimi aplikacjami.

    Gdy podano `on_close`, modal dostaje guzik „Zamknij aplikację”,
    który wywołuje `on_close` i chowa nakładkę.
    Zwraca False, gdy brakuje uprawnienia SYSTEM_ALERT_WINDOW lub coś
    poszło nie tak — wtedy wywołujący może pokazać fallback.
    Na głównym wątku (np. wątek Kivy) buduje nakładkę od razu, dzięki
    czemu wynik jest prawdziwy; poza nim (usługa p4a) budowa jest
    asynchroniczna i wynik jest optymistyczny.
    """
    global _OVERLAY
    try:
        if not can_draw_overlays():
            return False
        ctx = context()
        if _OVERLAY is not None:
            dismiss_overlay()
        if _on_main_thread():
            # jesteśmy na głównym wątku — zbuduj od razu i zwróć faktyczny wynik
            _build_views(ctx, title, message, timeout_s, on_close)
            return True

        def build_safe() -> None:
            # wyjątek na głównym wątku ubiłby cały proces usługi
            try:
                _build_views(ctx, title, message, timeout_s, on_close)
            except Exception:
                print("[overlay] błąd budowania nakładki:")
                import traceback

                traceback.print_exc()

        _post_to_main(build_safe)
        return True
    except Exception:
        print("[overlay] błąd w show_overlay_modal:")
        import traceback

        traceback.print_exc()
        return False


def dismiss_overlay() -> None:
    """Zamyka widoczną nakładkę (jeśli jakaś jest)."""
    global _OVERLAY
    if _OVERLAY is None:
        return
    if _on_main_thread():
        _OVERLAY.dismiss()  # bezpośrednio — kolejkowanie na tym wątku jest zbędne
    else:
        _post_to_main(_OVERLAY.dismiss)
