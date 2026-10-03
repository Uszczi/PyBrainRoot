"""Trwały magazyn wybranych aplikacji (SQLite 3).

Baza: getFilesDir()/pybrainroot.db — prywatny katalog aplikacji Androida.
SQLite jest w requirements p4a (dołącza je kivy) — `import sqlite3` działa
bez dodatkowych zmian w buildozer.spec.
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

_DB_NAME = "pybrainroot.db"


def _db_path() -> str:
    from pybrainroot.android_utils import context

    return os.path.join(context().getFilesDir().getAbsolutePath(), _DB_NAME)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Połączenie z bazą — po drodze tworzy tabelę, jeśli jej nie ma."""
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS monitored_apps ("
            " target TEXT PRIMARY KEY,"
            " name TEXT NOT NULL DEFAULT ''"
            ")"
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


def load_monitored_targets() -> set[str]:
    """Zbiór zapisanych celów monitorowania (nazwy pakietów)."""
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT target FROM monitored_apps").fetchall()
        return {str(row[0]) for row in rows}
    except Exception:
        return set()


def save_monitored_target(target: str, name: str = "") -> None:
    """Zapisuje (lub aktualizuje) monitorowaną aplikację."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO monitored_apps (target, name)"
                " VALUES (?, ?)",
                (target, name),
            )
            conn.commit()
    except Exception:
        pass


def delete_monitored_target(target: str) -> None:
    """Usuwa aplikację z listy monitorowanych."""
    try:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM monitored_apps WHERE target = ?", (target,)
            )
            conn.commit()
    except Exception:
        pass
