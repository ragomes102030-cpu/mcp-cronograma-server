# Skill — Cronograma/CPM/PERT (procedimento, não algoritmo)

**Quando usar:** planejar sequenciamento, conferir produtividade e durações e validar caminhos críticos ou baseline.

**Entradas obrigatórias:** atividades com `activity_id` estável e `eap_uid` quando disponível; quantitativo, unidade, produtividade/fonte, durações positivas (exceto marco), dependências TI/II/TT/IT com lag, `calendar_id` e convenção temporal.

**Tools públicas:** `calcular_duracao_com_evidencia`, `calcular_cpm_com_evidencia`. **Privadas somente com autorização:** `criar_atividade`, `criar_dependencia`, `validar_dependencias`, `calcular_caminho_critico`, `salvar_baseline`, `comparar_baseline`, `curva_s`.

**Validações:** rede não vazia para modelos multiatividade, IDs existentes, sem ciclos/orfandade, finitude, precedências e lag, passagem cedo/tarde, folga livre/total, caminhos críticos múltiplos, compatibilidade de unidades e consistência de calendário.

**Revisão humana:** produtividade, restrições legais/operacionais, feriados/jornada, datas contratuais, baseline aprovada e vínculo EAP não verificado automaticamente.

**Erros bloqueantes:** ciclo, dependência órfã, duração inválida, divergência de calendário, evidência incompleta ou projeto misturado. Nunca persistir baseline ou atualizar cronograma automaticamente por pedido genérico.

**Saída:** durações, ES/EF/LS/LF, folga total/livre, caminho(s) crítico(s), origem, tolerância, versão, SHA, datas relativas, convenção temporal e advertências. Motor determinístico executa cálculos; skill não os replica.
