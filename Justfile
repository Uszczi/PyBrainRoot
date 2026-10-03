# UI na desktopie (Linux) z symulowanymi częściami Androida.
# Na Waylandzie przejmujemy SDL2 systemowym (sdl2-compat ma sterownik
# wayland, dołączony do kivy nie) — bez tego okno idzie przez XWayland
# i kompozytor skaluje je 2x (pikselowe teksty na monitorach HiDPI).
dev:
    LD_PRELOAD=/usr/lib/libSDL2-2.0.so.0 SDL_VIDEODRIVER=wayland .venv/bin/python desktop_main.py

# fallback przez X11/XWayland (np. gdy brak systemowego libSDL2)
dev-x11:
    .venv/bin/python desktop_main.py

apk:
    VIRTUAL_ENV="$HOME/.local/share/uv/tools/buildozer" buildozer android debug

run-mobile:
    VIRTUAL_ENV="$HOME/.local/share/uv/tools/buildozer" buildozer android debug deploy run

logcat:
    adb logcat -v time *:S python:V monitor:V AndroidRuntime:E

logcat-dump:
    adb logcat -d -v time *:S python:V monitor:V AndroidRuntime:E
