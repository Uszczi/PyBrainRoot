"""Punkt wejścia aplikacji (importowany przez main.py w katalogu źródłowym).

Logika aplikacji żyje w pybrainroot.app — ten moduł istnieje po to, by
główny plik main.py (wymagany przez python-for-android) nie zmieniał się.
"""

from pybrainroot.app import main  # noqa: F401

__all__ = ["main"]
