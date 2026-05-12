# Estrategia Abrangente de Testes

## Objetivo
Validar funcionalidade, robustez, desempenho e disponibilidade do sistema de Arquivo Digital com cobertura de:
- casos de uso normais,
- casos extremos,
- situacoes de erro e falha.

## Piramide de testes
- Unitarios: regras de negocio e funcoes auxiliares.
- Integracao: fluxos HTTP + ORM + permissao + auditoria.
- Carga: capacidade nominal sob uso concorrente.
- Estresse: identificacao de limite operacional e recuperacao.

## Cenarios criticos obrigatorios
- Upload/confirmacao/listagem de documentos.
- Busca textual com OCR.
- Acoes em lote (adicionar/mover/excluir).
- Exclusao de caixa com desvinculacao de documentos.
- Registro de logs de auditoria.
- Controle de permissao por acao.

## Ambientes dedicados
- `dev-test`: feedback rapido (unitarios/integracao).
- `staging-perf`: carga nominal e validacao de p95/p99.
- `staging-stress`: estresse prolongado e picos.

## Dados simulados
Comando de seed:
```bash
python manage.py gerar_dados_teste --usuarios 20 --caixas 100 --documentos 5000 --seed 42
```

## Metricas e SLOs de referencia
- Tempo de resposta:
  - normal: `p95 < 800ms`, `p99 < 1500ms`.
  - estresse: `p95 < 1500ms`, `p99 < 3000ms`.
- Taxa de erro:
  - normal: `< 1%`.
  - estresse: `< 3%`.
- Disponibilidade na janela de teste: `>= 99.5%`.
- Integridade: `0` perda de documento e `100%` de operacoes criticas auditadas.

## Execucao automatizada sugerida
1. PR:
   - unitarios + integracao critica + lint.
2. Merge:
   - suite completa funcional.
3. Noturno:
   - carga curta + export de resumo.
4. Semanal:
   - estresse/soak + relatorio consolidado.

## Monitoramento de desempenho
- Aplicacao:
  - latencia por endpoint,
  - taxa de erro 4xx/5xx,
  - throughput (req/s).
- Infra:
  - CPU, memoria, disco e I/O.
- Banco:
  - query lenta, lock, conexoes ativas.

## Riscos e alertas de release
Bloquear release quando:
- erro acima do threshold,
- p95/p99 acima do limite aceito,
- inconsistencias de integridade de dados,
- falhas sem mitigacao definida.
