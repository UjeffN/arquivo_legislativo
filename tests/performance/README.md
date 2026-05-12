# Testes de Carga e Estresse (k6)

## Pre-requisitos
- k6 instalado na maquina de teste.
- Ambiente `staging-perf` ativo e isolado.
- Usuario de teste com acesso aos modulos de documentos e caixas.

## Variaveis de ambiente
- `BASE_URL`: URL base com prefixo `/arquivo` (ex.: `https://sistemas.parauapebas.pa.leg.br/arquivo`)
- `USERNAME`: usuario de teste
- `PASSWORD`: senha do usuario de teste

## Execucao: carga nominal
```bash
k6 run \
  -e BASE_URL="http://localhost:8000/arquivo" \
  -e USERNAME="admin" \
  -e PASSWORD="admin" \
  --summary-export=tests/performance/results/load-summary.json \
  tests/performance/load_test.js
```

## Execucao: estresse progressivo
```bash
k6 run \
  -e BASE_URL="http://localhost:8000/arquivo" \
  -e USERNAME="admin" \
  -e PASSWORD="admin" \
  --summary-export=tests/performance/results/stress-summary.json \
  tests/performance/stress_test.js
```

## Metricas avaliadas
- `http_req_duration` (p95 e p99)
- `http_req_failed` (taxa de erro)
- `checks` (sucesso das verificacoes)
- Throughput por endpoint (req/s no resumo do k6)

## Criterios de aceitacao sugeridos
- Carga: `p95 < 800ms`, `p99 < 1500ms`, `erro < 1%`.
- Estresse: `p95 < 1500ms`, `p99 < 3000ms`, `erro < 3%`.
- Integridade: sem perda de documentos nem inconsistencias em logs de auditoria.

## Integracao com monitoramento
- Coletar durante o teste:
  - CPU/memoria do host.
  - Uso de disco e I/O.
  - conexoes e locks do banco.
  - latencia e erros HTTP por rota.
- Relacionar os graficos de monitoramento com os picos de carga do k6.
