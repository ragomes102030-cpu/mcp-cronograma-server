"""Real libsql-client SDK integration with disposable local database only.

This verifies the file:// SDK transport, not remote Turso HTTP.
"""
import sqlite3

import libsql_client
import pytest


def test_libsql_sdk_batch_atomicity_on_failure_and_success(tmp_path):
    path = tmp_path / "isolated.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE baseline (id TEXT PRIMARY KEY, project_id TEXT NOT NULL);
            CREATE TABLE baseline_atividade (
                baseline_id TEXT NOT NULL, atividade_id TEXT NOT NULL,
                PRIMARY KEY (baseline_id, atividade_id)
            );
            CREATE TABLE baseline_ativa (
                project_id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL
            );
            INSERT INTO baseline VALUES ('old', 'test-project');
            INSERT INTO baseline_ativa VALUES ('test-project', 'old');
        """)
    client = libsql_client.create_client_sync("file:" + str(path))
    try:
        with pytest.raises(Exception):
            client.batch([
                ("INSERT INTO baseline VALUES (?, ?)", ["new", "test-project"]),
                ("INSERT INTO baseline_atividade VALUES (?, ?)", ["new", "a1"]),
                ("INSERT INTO baseline_atividade VALUES (?, ?)", ["new", "a1"]),
                ("UPDATE baseline_ativa SET baseline_id=? WHERE project_id=?",
                 ["new", "test-project"]),
            ])
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT id FROM baseline ORDER BY id").fetchall() == [("old",)]
            assert conn.execute("SELECT COUNT(*) FROM baseline_atividade").fetchone()[0] == 0
            assert conn.execute(
                "SELECT baseline_id FROM baseline_ativa WHERE project_id='test-project'"
            ).fetchone()[0] == "old"
        client.batch([
            ("INSERT INTO baseline VALUES (?, ?)", ["new", "test-project"]),
            ("INSERT INTO baseline_atividade VALUES (?, ?)", ["new", "a1"]),
            ("UPDATE baseline_ativa SET baseline_id=? WHERE project_id=?",
             ["new", "test-project"]),
        ])
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM baseline").fetchone()[0] == 2
            assert conn.execute(
                "SELECT baseline_id FROM baseline_ativa WHERE project_id='test-project'"
            ).fetchone()[0] == "new"
    finally:
        client.close()
