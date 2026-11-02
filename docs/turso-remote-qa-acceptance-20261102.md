# Homologação remota de Turso — 2026-11-02

**Resultado: APROVADO para contrato de persistência e transações do modelo.**

## Recursos usados

- Banco de dados **independente**: `qa-cronograma-20261102`, criado em Turso Cloud via integração Vercel, plano Starter gratuito, recurso `store_C6LAuAINDAuGLrJc`.
- Projeto de execução **QA isolado**: `arquimedes-cronograma-qa-runner` (Vercel `prj_JLxZLgUE1gLoVNTNb9SAcZLCRuKp`), conectado apenas ao novo banco QA.
- Aplicação principal de produção e seu banco **não utilizados para escritas de teste**.
- Branch temporária `qa/turso-e2e-20261102` com ferramenta de diagnóstico protegida por ID de projeto, nome de banco, branch, opção de escrita e cabeçalho de autorização.
- Rotas e arquivos de teste temporários removidos da branch após a validação; proteção SSO no projeto QA habilitada para todos os deployments e permissão de escrita do teste desativada para novas implantações.

## Resultados de operações remotas reais

| Verificação no banco QA remoto | `libsql-client` (legado) | `libsql` (novo) |
|---|---|---|
| `SELECT 1` real por HTTP | APROVADO | APROVADO |
| Inicialização e consulta das seis tabelas | APROVADO | APROVADO |
| Inserção e consulta de duas atividades | APROVADO | APROVADO |
| Criação e auditoria de dependência | APROVADO | APROVADO |
| Duas baselines; preservação do histórico e uma ativa | APROVADO | APROVADO |
| Falha na segunda instrução do batch; **nenhuma** persistida | APROVADO | APROVADO |
| Bloqueio de exclusão com dependência e posterior exclusão correta | APROVADO | APROVADO |

**Resultado HTTP:** 200 com `ok: true`, **7 verificações aprovadas em cada driver**, `cleaned: true`.

Projetos efêmeros e exclusivos dos testes:
- Legado: `qa-remote-0f6c6508a400`.
- Novo: `qa-remote-3e3b44c0f29a`.

Os registros criados foram removidos no final de cada teste. O schema QA permanece para regressões futuras.

## Limites do escopo aprovado

- A EAP foi validada por **stub isolado no runner QA**, sem consultar ou alterar o MCP EAP real.
- Testes foram executados sobre o **modelo de persistência do cronograma**, não uma sessão completa de JSON-RPC MCP privado com autenticação.
- A suíte de GitHub Actions manual `turso-disposable-qa.yml` continua disponível, mas ainda requer secrets independentes no GitHub; a homologação real deste documento foi executada em um runner Vercel QA com suas próprias credenciais sensíveis.
- `TURSO_DRIVER` não foi configurado no serviço real; o driver **legado continua padrão** em produção.
- A habilitação do driver novo em produção deve ser feita em alteração controlada, com observabilidade e rollback.

## Evidências técnicas

- Criação do banco QA confirmou `status=available`, `externalResourceStatus=ready` e plano `$0/month`.
- Readiness do QA runner retornou `project_ok=true`, `qa_host_ok=true`, `db_token_present=true`, branch correta e escrita isolada explicitamente habilitada.
- Ambos os POSTs autenticados contra a rota temporária retornaram `HTTP 200`, `ok=true` e `cleaned=true`.
- Após testes, o projeto QA recebeu SSO para todos os deployments; `QA_E2E_ALLOW` foi desabilitada para novas implantações, e a branch QA restaurou `api/index.py` e excluiu `api/qa_probe.py`.
- **Nenhuma credencial, URL de banco completa ou token de autenticação** foi adicionado a este relatório.

Conclusão: a falha anterior de inicialização do Turso está resolvida, e o caminho real de persistência, revisões de baselines e rollback foi homologado **nos dois SDKs** com banco QA independente.
