import models


def test_migracao_legado_preserva_todos_e_elege_ultimo(db):
    from models.db import _connect
    with _connect() as conn:
        conn.execute("INSERT INTO baseline (id, project_id, nome, criado_em) VALUES (?, ?, ?, ?)",
                     ("antiga", "obra-x", "Rev 0", "2026-01-01 00:00:00"))
        conn.execute("INSERT INTO baseline (id, project_id, nome, criado_em) VALUES (?, ?, ?, ?)",
                     ("nova", "obra-x", "Rev 1", "2026-02-01 00:00:00"))
        conn.commit()
    models.init_db()
    itens = db.listar_baselines("obra-x")
    assert len(itens) == 2
    assert {x["id"] for x in itens if x["ativa"]} == {"nova"}
    models.init_db()
    assert len(db.listar_baselines("obra-x")) == 2
    assert {x["id"] for x in db.listar_baselines("obra-x") if x["ativa"]} == {"nova"}


def test_migracao_nao_sobrescreve_ativa_existente(db):
    from models.db import _connect
    with _connect() as conn:
        conn.execute("INSERT INTO baseline (id, project_id, nome) VALUES ('primeira', 'obra-y', 'Rev 0')")
        conn.execute("INSERT INTO baseline_ativa (project_id, baseline_id) VALUES ('obra-y', 'primeira')")
        conn.execute("INSERT INTO baseline (id, project_id, nome) VALUES ('segunda', 'obra-y', 'Rev 1')")
        conn.commit()
    models.init_db()
    assert {x["id"] for x in db.listar_baselines("obra-y") if x["ativa"]} == {"primeira"}
