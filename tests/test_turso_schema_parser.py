"""Regression: remote Turso executescript must honor SQLite statement boundaries.

Use the sqlite3 parser and an in-memory fake HTTP result. No remote DB calls,
credentials, or mutations of a real database occur.
"""
from types import SimpleNamespace
import sqlite3

from models import db


class _FakeTurso:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.statements = []

    def execute(self, sql, args):
        self.statements.append(sql)
        cur = self.db.execute(sql, args)
        return SimpleNamespace(
            columns=[col[0] for col in cur.description] if cur.description else [],
            rows=cur.fetchall() if cur.description else [],
        )


def test_schema_comment_semicolon_does_not_corrupt_remote_ddl(monkeypatch):
    fake = _FakeTurso()
    monkeypatch.setattr(db, "_TURSO_URL", "libsql://isolated.example")
    monkeypatch.setattr(db, "_get_turso_client", lambda: fake)

    db.init_db()  # Schema DDL and additive migration on in-memory SQLite only.
    tables = {r[0] for r in fake.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"atividade", "dependencia", "baseline", "baseline_ativa",
            "baseline_atividade", "idempotency"} <= tables
    assert any("Ponteiro unico por projeto;" in sql
               and "CREATE TABLE IF NOT EXISTS baseline_ativa" in sql
               for sql in fake.statements)


def test_semicolons_inside_comments_and_literals_remain_one_statement(monkeypatch):
    fake = _FakeTurso()
    monkeypatch.setattr(db, "_get_turso_client", lambda: fake)
    conn = db._TursoConn()

    conn.executescript(
        "-- header; not a statement boundary\n"
        "CREATE TABLE quoted (value TEXT DEFAULT 'a;b');\n"
        "/* block; comment */ CREATE INDEX idx_quoted ON quoted(value);\n"
        "INSERT INTO quoted(value) VALUES ('x;y');"
    )
    assert fake.db.execute("SELECT value FROM quoted").fetchone()[0] == "x;y"
    assert len(fake.statements) == 3
    assert all("CREATE TABLE quoted" in fake.statements[0] for _ in [0])
