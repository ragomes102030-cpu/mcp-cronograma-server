# mcp-cronograma-server

Servidor MCP de cronograma (PERT/CPM), seguindo o roteiro de
**"Planejamento e Controle de Obras"**, de Aldo Dórea Mattos: atividades →
durações → precedência → rede → caminho crítico → cronograma/folgas, mais
linha de base e curva S.

Complementa o [mcp-eap-server](https://github.com/ragomes102030-cpu/mcp-eap-server):
cada atividade referencia um nó da EAP via `eap_ref` (uid ou eap_id), mas os
dois serviços não compartilham banco de dados — são domínios de dados
separados de propósito (ver decisão de arquitetura abaixo).

## Por que um servidor separado do mcp-eap-server?

- **Ciclo de vida diferente**: a EAP muda pouco depois de definida;
  cronograma muda a cada atualização de progresso, recalculando caminho
  crítico e folgas de potencialmente toda a rede.
- **Domínio de dados diferente**: atividade, duração, precedência, rede,
  folga e baseline são um domínio inteiro — não um apêndice da EAP.
- Um bug de recálculo de cronograma não deve conseguir travar consultas de
  EAP (nem vice-versa) por estarem no mesmo processo.

## Tools

| Categoria | Tools |
|---|---|
| Atividades | `criar_atividade`, `atualizar_atividade`, `listar_atividades`, `deletar_atividade` |
| Dependências | `criar_dependencia`, `listar_dependencias`, `deletar_dependencia`, `validar_dependencias` |
| Caminho crítico | `calcular_caminho_critico` |
| Baseline | `salvar_baseline`, `listar_baselines`, `comparar_baseline` |
| Curva S | `curva_s` |

## Duração: determinística ou PERT

Passe `duracao_dias` diretamente, ou `duracao_otimista`/`duracao_provavel`/
`duracao_pessimista` — a duração esperada é calculada automaticamente por
`(O + 4M + P) / 6` (fórmula PERT clássica).

## Dependências (precedência)

4 tipos, com `lag_dias` (deslocamento, pode ser negativo pra sobreposição):
- `TI` (término-início, default): sucessora só começa quando a predecessora termina
- `II` (início-início): sucessora começa quando a predecessora começa
- `TT` (término-término): sucessora termina quando a predecessora termina
- `IT` (início-término): sucessora termina quando a predecessora começa

Toda dependência é validada contra ciclo na criação (`criar_dependencia`
rejeita se fechar um ciclo na rede).

## O que NÃO é escopo deste servidor (v1)

- **Custo/orçamento** (valores R$, composições de preço) — outro domínio,
  que também referenciaria `eap_id` como estrangeiro.
- **Recursos/equipe** (alocação de mão-de-obra/equipamento).
- **CCPM** (corrente crítica) — abordagem alternativa ao CPM tradicional,
  não implementada.
- **Validação cruzada ao vivo contra o mcp-eap-server**: `eap_ref` é
  aceito como string opaca, sem checar se o nó realmente existe na EAP no
  momento da criação da atividade (ver TODO em `models/db.py`).
- **Turso/persistência remota**: usa SQLite local (mesma ressalva do
  mcp-eap-server sobre efemeridade em disco não-persistente do Render).
- **Autenticação**: mesma pendência do mcp-eap-server, ainda não resolvida
  em nenhum dos dois serviços.

## Rodando localmente

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -q
uvicorn server:app --reload
```
