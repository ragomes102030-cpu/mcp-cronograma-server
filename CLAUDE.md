# Guia de arquitetura — mcp-cronograma-server

## Camadas

| Arquivo | Papel |
|---|---|
| `models/` | Camada de dados: `db.py` (schema/conexão), `atividades.py`, `dependencias.py`, `cpm.py` (caminho crítico), `calendario.py` (datas reais), `baseline.py`, `curva_s.py`, `idempotencia.py` |
| `schemas.py` | Schemas Pydantic de saída |
| `server.py` | FastMCP: as tools, wrapper de erro `_seguro`, idempotência |

**Camadas rígidas**: `server.py` nunca toca SQL direto; `models/` nunca
importa `mcp`/`schemas`. Dentro de `models/`, `cpm.py` só lê (via
`listar_atividades`/`listar_dependencias`) e escreve resultado via
`salvar_resultado_cpm` — não faz SQL direto.

## Persistência: Turso em produção

Igual ao mcp-eap-server: sem `TURSO_URL`/`TURSO_TOKEN`, usa SQLite local —
que **some a cada redeploy no Render** (disco não-persistente). Configure
essas duas variáveis de ambiente no Render pra persistir de verdade.
Use um banco Turso **separado** do mcp-eap-server (bancos diferentes, não
o mesmo — os dois serviços não devem compartilhar schema nem dados).

## Armadilha já conhecida: `DB_PATH` e monkeypatch nos testes

`models/db.py._connect()` resolve `DB_PATH` via `from . import DB_PATH`
(não a constante do próprio módulo) de propósito. Se você "simplificar"
isso pra `sqlite3.connect(DB_PATH)` direto, os testes que fazem
`monkeypatch.setattr(models, "DB_PATH", ...)` (ver `tests/conftest.py`)
param de isolar o banco — esse exato bug já aconteceu no mcp-eap-server
irmão deste projeto quando ele virou pacote, e a lição foi replicada aqui
preventivamente.

## Migração nunca derruba o startup

`init_db()` roda na importação do módulo `server.py` — antes do `uvicorn`
aceitar qualquer requisição. Uma migração que levanta exceção aqui derruba
o processo inteiro antes dele subir. Isso já causou um incidente real de
produção no mcp-eap-server (ver histórico de commits de lá,
"fix(critico): migracao nunca mais derruba o startup do servidor"). Neste
projeto o schema é criado de uma vez via `executescript(SCHEMA)` com
`CREATE TABLE IF NOT EXISTS`/`CREATE INDEX IF NOT EXISTS` — não há
`ALTER TABLE` incremental ainda. Se algum dia adicionar uma migração
incremental aqui, siga o padrão do mcp-eap-server: nunca `raise`, sempre
logar e continuar.

## Ordem de implementação do CPM (`models/cpm.py`)

1. Ordenação topológica (Kahn) — detecta ciclo (não deveria existir, já que
   `criar_dependencia` bloqueia na criação, mas serve de segunda linha de
   defesa contra dado importado direto no banco).
2. Forward pass (ES/EF) na ordem topológica.
3. Backward pass (LS/LF) na ordem topológica inversa, ancorado no maior EF.
4. Folga total = LS - ES; folga livre = ES da sucessora mais cedo - EF;
   crítica quando folga total ≈ 0 (tolerância de ponto flutuante).

Suporta as 4 relações de dependência (TI/II/TT/IT) com lag — a lógica de
cada uma está duplicada entre forward e backward pass de propósito (são
fórmulas espelhadas, não a mesma fórmula) — não tente unificar num único
helper sem testar contra os 4 tipos.

## Integração com o mcp-eap-server

`eap_ref` é uma string opaca (uid ou eap_id do outro servidor) — este
projeto NÃO valida ao vivo se o nó existe lá (ver TODO em `models/db.py` e
seção "O que não é escopo" do README). Se for implementar essa validação,
prefira um cliente HTTP simples chamando a tool `get_eap_node` do
mcp-eap-server via streamable-http, com timeout curto e falha graciosa
(não bloquear criação de atividade se o outro serviço estiver fora do ar
— apenas avisar).

## Testes

`pytest tests/` com gate de cobertura 70% em `models/` (hoje ~85%).
`tests/test_cpm.py` valida o cálculo contra um exemplo clássico de
livro-texto com valores exatos conhecidos (A→B→D crítico, C com folga 1) —
qualquer mudança no algoritmo deve continuar batendo com esses valores, ou
justificar por que os valores esperados mudaram.
