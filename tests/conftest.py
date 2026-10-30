import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", tmp_path / "teste.db")
    # A validação remota é testada separadamente em test_eap_traceability.
    # Nenhuma chamada HTTP externa ou bypass de validação é permitido na produção.
    from models import atividades
    monkeypatch.setattr(
        atividades, "validar_eap_ref",
        lambda project_id, eap_ref: {"encontrado": True, "eap_id": eap_ref},
    )
    models.init_db()
    return models
