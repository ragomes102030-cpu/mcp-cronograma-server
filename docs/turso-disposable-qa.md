# Homologação Turso descartável — MCP Cronograma

**Status:** a correção de conexão/importação e a verificação das seis tabelas no
banco existente foram confirmadas. **A escrita remota completa ainda precisa
ser executada em banco QA independente**, sem reutilizar credenciais de produção.

## 1. Criar banco novo e vazio (Turso Cloud)

Use uma conta administrativa Turso autenticada em ambiente seguro. Crie um banco
**independente, novo e vazio**, chamado por exemplo
`qa-cronograma-20261102`. **Não copie nem ramifique o banco de produção**:
o teste faz DDL, INSERT, UPDATE e DELETE no banco QA.

A URL e o token desse banco QA devem ficar apenas no seu terminal seguro ou
em secrets protegidos do CI. Nunca cole credenciais no GitHub, no chat ou em logs.

## 2. Configurar o ambiente QA

- `TURSO_TEST_DATABASE_URL`: URL libsql/https do **novo** banco QA.
- `TURSO_TEST_AUTH_TOKEN`: token exclusivamente para esse banco QA.
- `TURSO_PRODUCTION_DATABASE_URL`: **apenas URL** do banco real, para impedir
  direcionamento acidental (não colocar o token de produção).
- `TURSO_REMOTE_TEST_CONFIRM=YES_DISPOSABLE_WRITES`: confirmação explícita.

O teste interrompe a execução se faltar confirmação, se os hostnames forem
iguais, se a URL não usar HTTPS ou se o nome do banco QA não começar com
`qa-`, `test-`, `sandbox-` ou `disposable-`.

## 3. Executar

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/test_turso_disposable_roundtrip.py -m remote_turso -q
```

O mesmo arquivo contém um ensaio offline com SQLite real por trás do adaptador
Turso. Esse ensaio roda na CI normal, sem rede e sem credenciais.

## 4. Critérios de aprovação

1. Inicializar o esquema no banco QA novo.
2. Criar e consultar duas atividades com EAP simulada **somente no teste**.
3. Criar e validar uma dependência.
4. Capturar duas baselines, preservar a anterior e manter uma única ativa.
5. Simular falha de transação e comprovar que a revisão ativa não mudou.
6. Atualizar atividade, recusar exclusão com dependência, remover vínculo
   e excluir atividade.
7. Limpar apenas o projeto QA de identificador único.

O teste é no **modelo de dados**. Ainda deve ser complementado por homologação
MCP autenticada no ambiente QA. A validação EAP é simulada apenas dentro do
processo de teste: a aplicação publicada continua fail-closed.

**Nunca** execute o comando de homologação remota apontando para o banco de
produção. Exclua o banco descartável pelo painel Turso após a aprovação.
