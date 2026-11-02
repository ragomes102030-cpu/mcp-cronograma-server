# Homologação E2E dos três MCPs privados — procedimento de QA

**Estado do teste remoto:** preparado e bloqueado até existir ambiente QA com endpoints
privados implantados e credenciais próprias. **Não há execução remota aprovada
registrada neste documento.** A homologação pública anterior não confirma
persistência nos três servidores.

## Fluxo executado pelo runner

`scripts/qa_three_private_mcps.py` prepara uma obra **exclusivamente fictícia**
com ID aleatório `qa-integracao-...`, exclusivamente nos três endereços QA
pré-definidos. Regras de falha segura:

1. Todas as três URLs precisam usar HTTPS, sufixo `/mcp` e **host exato
   (sem subdomínios parecidos)** dos projetos verificados:
   `arquimedes-eap-private-qa-20261102.vercel.app`,
   `arquimedes-cronograma-qa-runner.vercel.app` e
   `arquimedes-lob-private-qa-20261102.vercel.app`.
2. Não aceita endpoints públicos, aliases de produção, credenciais na URL,
   parâmetros de URL ou redirecionamentos HTTP.
3. Exige `--execute`, `QA_PRIVATE_E2E_CONFIRM=YES_QA_ONLY` e **três tokens
   Bearer distintos de produção**, definidos apenas no ambiente de execução.
   Ausência de qualquer requisito impede a primeira requisição.
4. Negocia JSON-RPC MCP `initialize` / `notifications/initialized` /
   `tools/list` e exige o catálogo privado esperado antes de escrever dados.
5. O MCP EAP cria projeto, raiz, agrupamento e duas folhas com UIDs. O MCP
   Cronograma grava cinco atividades vinculadas às referências EAP, cinco
   dependências, calcula CPM persistido e salva uma baseline. O MCP Gantt/LOB
   calcula as duas unidades e gera um Excel a partir das datas reais do CPM.
6. O runner exige CPM de 16 dias, LOB de 14 dias após mobilização (2 dias)
   e quatro comparações de início/término por pavimento e serviço sem divergência.

**Retenção intencional:** o projeto QA e sua baseline permanecem no banco QA
porque o Cronograma privado **não oferece uma API de exclusão transacional de
projeto e baseline**. O runner não tenta apagar projetos e não afirma limpeza
concluída. O banco QA deve ser descartado após auditoria ou receber uma operação
de limpeza devidamente testada. Não se deve executá-lo contra dados de clientes.

## Condições para executar

No repositório GitHub `ragomes102030-cpu/mcp-cronograma-server`, configurar
três secrets do Actions: `QA_EAP_MCP_TOKEN`,
`QA_CRONOGRAMA_MCP_TOKEN` e `QA_LOB_MCP_TOKEN`. Esses valores precisam
ser os **MCP_API_TOKEN dos projetos QA**, não tokens do banco Turso.

O Cronograma QA também precisa configurar `EAP_SERVER_URL` com a
**origem HTTPS sem `/mcp`** do EAP QA, por exemplo
`https://arquimedes-eap-private-qa-20261102-EXEMPLO.vercel.app`. Seu
`models/atividades.py` acrescenta automaticamente
`/internal/eap-node?project_id=...&eap_ref=...`; acrescentar `/mcp` na
variável causaria HTTP 404. `EAP_API_TOKEN` deve ser exatamente o
`MCP_API_TOKEN` do mesmo EAP QA. Os bancos EAP e Cronograma precisam ser
descartáveis e diferentes dos bancos de produção.

Acionar manualmente o workflow `three-private-mcp-disposable-qa.yml` com
`confirm=YES_QA_ONLY` e **URLs canônicas fixas** dos projetos QA,
todas terminando em `/mcp` (não usar URLs de deployments de hash variável). Os logs não imprimem tokens. O workflow produz os artefatos
`gantt_qa_privado.xlsx` e `relatorio_qa_privado.json`.

**Pré-verificação sem escrever:** `python scripts/qa_three_private_mcps.py`
retorna dry-run sem consumir rede. Executar
`pytest -q tests/test_private_three_mcp_qa_runner.py` exercita os guards e
o fluxo usando dublês totalmente em memória. Esses testes de dublê **não
constituem homologação remota**.

## Critérios para declarar APROVADO

- Endpoint EAP QA privado aceita Bearer e persiste projeto/nós; IDs/UIDs
  são recuperados pela leitura subsequente.
- Cronograma QA privado consulta EAP QA para validar cada referência. Nunca
  usa `EAP_SERVER_URL` do serviço EAP de produção.
- Atividades, dependências, CPM e baseline persistem apenas no banco QA.
- Datas e inícios CPM × LOB concordam em 4/4 serviços-local.
- Gantt privado entrega arquivo XLSX válido e o relatório JSON existe.
- Nenhuma escrita no projeto `default`, na Plataforma Obras ou em bancos
  e serviços de produção.
- Logs de sucesso e de falha deixam os IDs de teste rastreáveis.

**Não abrangido:** cálculo de custos, regra contratual dos 100% da EAP,
autorização multiusuário, backups da obra, homologação de produção.
