"""Opt-in adapter for Turso's maintained `libsql` Python DB-API driver.

The legacy driver remains default until remote disposable database acceptance.
Each operation owns and closes its connection; batches share a single
connection and roll back completely if any statement fails.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class ModernTursoClient:
    def __init__(self, url: str, auth_token: str):
        if not url.startswith("https://"):
            raise ValueError("Modern remote Turso requires HTTPS.")
        if not auth_token:
            raise ValueError("Modern remote Turso requires an auth token.")
        self.url = url
        self._auth_token = auth_token

    def _open(self) -> Any:
        import libsql
        return libsql.connect(database=self.url, auth_token=self._auth_token)

    def execute(self, sql: str, params: list | tuple = ()):
        conn = self._open()
        try:
            cur = conn.execute(sql, tuple(params))
            columns = [col[0] for col in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            conn.commit()
            return SimpleNamespace(columns=columns, rows=rows)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def batch(self, statements: list[tuple[str, list]]):
        """Atomic baseline revision; never split over separate connections."""
        conn = self._open()
        try:
            for sql, params in statements:
                conn.execute(sql, tuple(params))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self):
        """Compatibility with the legacy singleton client lifecycle."""
        return None
